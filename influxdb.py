import pandas as pd
import requests

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

client = InfluxDBClient(
    url="http://192.168.32.70:8086",
    token="my-super-secret-auth-token",
    org="my-org",
    bucket="my-bucket",
)