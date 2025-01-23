import pandas as pd
import requests
import datetime


class InfluxDBClient:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.headers = {"Authorization": f"Token {token}"}

    def _convert_timestamp(self, timestamp):
        """
        Timestampをナノ秒精度のUnixタイムスタンプに変換する
        """
        if isinstance(timestamp, pd.Timestamp):
            return int(timestamp.timestamp() * 1e9)  # ナノ秒精度に変換
        raise ValueError("Invalid timestamp format. Must be pandas.Timestamp.")

    def write(self, measurement, fields, tags=None, timestamp=None):
        tags = tags or {}
        tag_set = ','.join([f"{k}={v}" for k, v in tags.items()])
        field_set = ','.join([f"{k}={v}" for k, v in fields.items()])
        
        # タイムスタンプを変換
        if timestamp is not None:
            timestamp = self._convert_timestamp(timestamp)
        # print(timestamp)
        data = f"{measurement},{tag_set} {field_set} {timestamp}"
        params = {
            "org": self.org,
            "bucket": self.bucket,
            "precision": "ns"  # ナノ秒精度を指定
        }
        try:
            response = requests.post(
                f"{self.url}/api/v2/write",
                params=params,
                data=data,
                headers=self.headers
            )
            assert response.status_code == 204, f"Failed to write data: {response.text}"
            return response
        except requests.RequestException as error:
            return error

    def execute_flux(self, flux_script):
        """
        Fluxスクリプトを /api/v2/query で実行する
        """
        url = f"{self.url}/api/v2/query"
        # InfluxDB 2.x の Flux 実行時は Content-Type: application/json で JSON ボディを送る
        headers = {
            **self.headers,
            "Content-Type": "application/json"
        }
        data = {
            "query": flux_script,
            "type": "flux"
        }
        try:
            response = requests.post(url, headers=headers, json=data)
            # ステータスコードとレスポンスを確認
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            return error

    def remove_old_records(self, measurement, product_id):
        """
        指定した measurement, product_id に一致するデータのうち、
        過去40日より古いレコードを削除する (delete 関数をFluxで実行)
        
        例:
          - measurement: "my_measurement"
          - product_id: "ABC123"
        """
        # 40日前までの時刻を計算
        now_utc = datetime.datetime.utcnow()
        older_than_40days = now_utc - datetime.timedelta(days=40)
        # ISO8601形式 (例: 2025-01-21T12:34:56.789012Z) に変換
        stop_time = older_than_40days.replace(microsecond=0).isoformat() + "Z"

        # InfluxDB 2.x のFlux delete 関数を使った削除スクリプト
        #   - start は十分古い日時を指定 (例: 1970-01-01T00:00:00Z)
        #   - stop に 40日前を指定
        flux_script = f'''
delete(
  bucket: "{self.bucket}",
  org: "{self.org}",
  predicate: (r) => r._measurement == "{measurement}" and r.product_id == "{product_id}",
  start: 1970-01-01T00:00:00Z,
  stop: {stop_time}
)
'''

        result = self.execute_flux(flux_script)
        return result
    
client = InfluxDBClient(
    url="http://192.168.32.70:8086",
    token="my-super-secret-auth-token",
    org="my-org",
    bucket="my-bucket",
)