from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import requests
import pandas as pd
import time

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    SSHException,
    NoValidConnectionsError
)
from typing import Optional

import io


@dataclass
class Region:
    name: str
    description: str


@dataclass
class InstanceSpecs:
    vcpus: int
    memory_gib: int
    storage_gib: int
    gpus: int


@dataclass
class InstanceType:
    name: str
    description: str
    gpu_description: str
    price_cents_per_hour: int
    specs: InstanceSpecs
    regions: List[Region]

    @property
    def price_per_hour(self) -> float:
        return self.price_cents_per_hour / 100

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'InstanceType':
        instance_data = data['instance_type']
        specs = InstanceSpecs(**instance_data['specs'])
        regions_data = data.get('regions_with_capacity_available') or [data.get('region')]
        regions = [Region(**region) for region in regions_data if region]
        return cls(
            name=instance_data['name'],
            description=instance_data['description'],
            gpu_description=instance_data['gpu_description'],
            price_cents_per_hour=instance_data['price_cents_per_hour'],
            specs=specs,
            regions=regions
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'gpu_description': self.gpu_description,
            'price_per_hour': self.price_per_hour,
            **self.specs.__dict__
        }


@dataclass
class Instance:
    id: str
    ip: str
    status: str
    hostname: str
    instance_type: InstanceType
    region: Region
    ssh_key_names: List[str]
    file_system_names: List[str]
    jupyter_token: Optional[str] = None
    jupyter_url: Optional[str] = None
    is_reserved: bool = False

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Instance':
        return cls(
            id=data['id'],
            ip=data.get('ip', ''),
            status=data['status'],
            hostname=data.get('hostname', ''),
            instance_type=InstanceType.from_api_response({'instance_type': data['instance_type']}),
            region=Region(**data['region']),
            ssh_key_names=data.get('ssh_key_names', []),
            file_system_names=data.get('file_system_names', []),
            jupyter_token=data.get('jupyter_token'),
            jupyter_url=data.get('jupyter_url'),
            is_reserved=data.get('is_reserved', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'ip': self.ip,
            'status': self.status,
            'hostname': self.hostname,
            'instance_type': self.instance_type.name,
            'description': self.instance_type.description,
            'price_per_hour': self.instance_type.price_per_hour,
            'region': self.region.name,
            'region_description': self.region.description,
            'ssh_keys': ','.join(self.ssh_key_names),
            'file_systems': ','.join(self.file_system_names),
            'jupyter_url': self.jupyter_url or ''
        }


@dataclass
class SSHKey:
    id: str
    name: str
    public_key: str
    private_key: Optional[str] = None


@dataclass
class FileSystem:
    id: str
    name: str
    description: str


class APIError(Exception):
    """基本的なAPIエラークラス"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"APIError {status_code}: {message}")


class UnauthorizedError(APIError):
    """401 Unauthorizedエラー"""
    pass


class ForbiddenError(APIError):
    """403 Forbiddenエラー"""
    pass


class NotFoundError(APIError):
    """404 Not Foundエラー"""
    pass


class LambdaCloudController:
    BASE_URL = 'https://cloud.lambdalabs.com/api/v1'

    def __init__(self, api_key: str):
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/{path}'
        try:
            response = requests.request(method, url, headers=self.headers, json=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            status = response.status_code
            try:
                error_message = response.json().get('error', {}).get('message', response.text)
            except ValueError:
                error_message = response.text

            if status == 401:
                raise UnauthorizedError(status, "Unauthorized: Invalid or missing API key.") from http_err
            elif status == 403:
                raise ForbiddenError(status, "Forbidden: You don't have permission to perform this action.") from http_err
            elif status == 404:
                raise NotFoundError(status, "Not Found: The requested resource does not exist.") from http_err
            else:
                raise APIError(status, error_message) from http_err

        try:
            return response.json()
        except ValueError:
            raise APIError(response.status_code, "Invalid JSON response")

    def launch_instance(self, region_name: str, instance_type_name: str, ssh_key_name: str, quantity: int = 1, name: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            'region_name': region_name,
            'instance_type_name': instance_type_name,
            'quantity': quantity,
            'ssh_key_names': [ssh_key_name],
        }
        if name:
            payload['name'] = name
        return self._make_request('POST', 'instance-operations/launch', payload)

    def launch_instance_wait(
        self,
        region_name: str,
        instance_type_name: str,
        ssh_key_name: str,
        quantity: int = 1,
        name: Optional[str] = None,
        timeout: int = 300,
        interval: int = 1
    ) -> List[Instance]:
        """
        インスタンスを起動し、ホスト名が設定されるまで待機します。
    
        Args:
            region_name (str): 起動するリージョンの名前。
            instance_type_name (str): 起動するインスタンスタイプの名前。
            ssh_key_name (str): 使用するSSHキーの名前。
            quantity (int, optional): 起動するインスタンスの数。デフォルトは1。
            name (Optional[str], optional): インスタンスの名前。デフォルトはNone。
            timeout (int, optional): 待機のタイムアウト時間（秒）。デフォルトは300秒。
            interval (int, optional): ポーリング間の待機時間（秒）。デフォルトは10秒。
    
        Returns:
            List[Instance]: 起動し、ホスト名が設定されたインスタンスのリスト。
    
        Raises:
            TimeoutError: ホスト名が設定されるまでにタイムアウトした場合。
            APIError: APIリクエスト中にエラーが発生した場合。
        """
        # インスタンスを起動
        response = self.launch_instance(region_name, instance_type_name, ssh_key_name, quantity, name)
        instance_ids = response.get('data', {}).get('instance_ids', [])
        if not instance_ids:
            raise APIError(500, "インスタンスIDが取得できませんでした。")
    
        end_time = time.time() + timeout
        ready_instances = []
    
        while time.time() < end_time:
            try:
                instances = self.list_instances()
                for item in instances.get('data', []):
                    if item['id'] in instance_ids and item.get('hostname'):
                        instance = Instance.from_api_response(item)
                        ready_instances.append(instance)
                if len(ready_instances) == len(instance_ids):
                    return ready_instances
            except APIError:
                pass
            time.sleep(interval)
    
        not_ready = [id for id in instance_ids if id not in [inst.id for inst in ready_instances]]
        raise TimeoutError(f"インスタンス {', '.join(not_ready)} のホスト名が設定されませんでした。")

    def launch_instance_wait_auto(self):
        # インスタンスを作成
        import datetime
        key_name = "key_" + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        key = self.add_ssh_key(key_name)
        
        instance_types_df = self.get_instance_types_df(sort_by="price_per_hour").head()
        instance_type = instance_types_df.iloc[0]
        args = {
            "region_name": instance_type.region,
            "instance_type_name": instance_type["name"],
            "ssh_key_name": key_name,
        }
        print("creating...", instance_type.to_dict())
        instance = self.launch_instance_wait(**args)
        return key, instance

    def terminate_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        return self._make_request('POST', 'instance-operations/terminate', {'instance_ids': instance_ids})

    def restart_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """指定されたインスタンスを再起動します。"""
        return self._make_request('POST', 'instance-operations/restart', {'instance_ids': instance_ids})

    def list_instances(self) -> Dict[str, Any]:
        return self._make_request('GET', "instances")

    def list_instances_df(self) -> pd.DataFrame:
        response = self.list_instances()
        data = response['data']
        instances = [Instance.from_api_response(item) for item in data]
        df = pd.DataFrame([instance.to_dict() for instance in instances])
        desired_columns = [
            'id', 'status', 'instance_type', 'description',
            'price_per_hour', 'region', 'region_description',
            'ip', 'hostname', 'ssh_keys', 'file_systems', 'jupyter_url'
        ]
        return df[desired_columns] if not df.empty else df

    def get_instance_types(self) -> List[InstanceType]:
        response = self._make_request('GET', 'instance-types')
        return [InstanceType.from_api_response(item) for item in response['data'].values()]

    def get_instance_types_df(self, sort_by: Optional[str] = None, ascending: bool = True) -> pd.DataFrame:
        """
        利用可能なインスタンスタイプをDataFrameで取得し、指定されたカラムでソートします。

        Args:
            sort_by (Optional[str]): ソートに使用するカラム名。指定しない場合はソートしません。
            ascending (bool): ソート順序。Trueなら昇順、Falseなら降順。デフォルトはTrue。

        Returns:
            pd.DataFrame: ソートされたインスタンスタイプのデータフレーム。
        """
        instance_types = self.get_instance_types()
        records = [
            {**instance.to_dict(), 'region': region.name, 'region_description': region.description}
            for instance in instance_types for region in instance.regions
        ]
        df = pd.DataFrame(records)
        
        if sort_by:
            if sort_by not in df.columns:
                raise ValueError(f"指定されたカラム '{sort_by}' は存在しません。利用可能なカラム: {', '.join(df.columns)}")
            df = df.sort_values(by=sort_by, ascending=ascending)
        
        return df

    def get_ssh_keys(self) -> List[SSHKey]:
        response = self._make_request('GET', 'ssh-keys')
        return [SSHKey(**item) for item in response['data']]

    def add_ssh_key(self, name: str, public_key: Optional[str] = None) -> SSHKey:
        payload = {'name': name}
        if public_key:
            payload['public_key'] = public_key
        response = self._make_request('POST', 'ssh-keys', payload)
        return SSHKey(**response['data'])

    def delete_ssh_key(self, ssh_key_id: str) -> Dict[str, Any]:
        return self._make_request('DELETE', f'ssh-keys/{ssh_key_id}')

    def list_file_systems(self) -> List[FileSystem]:
        response = self._make_request('GET', 'file-systems')
        return [FileSystem(**item) for item in response['data']]

    def find_instance_type(self, name: str) -> Optional[InstanceType]:
        return next((it for it in self.get_instance_types() if it.name == name), None)

    def find_available_regions(self, instance_type_name: str) -> List[str]:
        instance = self.find_instance_type(instance_type_name)
        return [region.name for region in instance.regions] if instance else []

    def delete_all_resources(self):
        instances = self.list_instances_df()
        # # 起動中のインスタンスをすべて削除
        if len(instances)>0:
            print(f"deleting vm {instances.id.tolist()}")
            self.terminate_instances(instances.id.values.tolist())
        else:
            print("Vms to delete not found")
        
        # 全ての鍵を削除
        keys = self.get_ssh_keys()
        for key in keys:
            print(f"deleting key {key.id}")
            self.delete_ssh_key(key.id)
            