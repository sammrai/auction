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

class SSHClientError(Exception):
    """基本的なSSHクライアントエラークラス"""
    pass


class SSHConnectionError(SSHClientError):
    """SSH接続エラー"""
    pass


class SSHAuthenticationError(SSHClientError):
    """SSH認証エラー"""
    pass


class SSHCommandError(SSHClientError):
    """SSHコマンド実行エラー"""
    def __init__(self, command: str, exit_status: int, stdout: str, stderr: str):
        self.command = command
        self.exit_status = exit_status
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command '{command}' failed with status {exit_status}:\nSTDOUT: {stdout}\nSTDERR: {stderr}")


class SSHClient:
    """
    SSH接続を管理し、リモートインスタンス上でコマンドを実行するクラス。
    
    使用例:
        key_str = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        with SSHClient(host='198.51.100.2', username='ubuntu', key_str=key_str) as ssh:
            output = ssh.cmd('ls -la')
            print(output)
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_str: str,
        port: int = 22,
        timeout: Optional[float] = None,
        retry_delay: float = 5.0,
    ):
        """
        SSHClientの初期化。
        
        Args:
            host (str): 接続先のホスト名またはIPアドレス。
            username (str): SSHユーザー名。
            key_str (str): SSHプライベートキーの文字列。
            port (int, optional): SSHポート番号。デフォルトは22。
            timeout (Optional[float], optional): 接続タイムアウト時間（秒）。デフォルトはNone。
        """
        self.host = host
        self.username = username
        self.key_str = key_str
        self.port = port
        self.timeout = timeout
        self.client = None  # type: Optional[paramiko.SSHClient]
        self.retry_delay = retry_delay

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _load_private_key(self) -> paramiko.PKey:
        """
        秘密鍵の文字列からParamikoのPKeyオブジェクトを生成します。
        
        Returns:
            paramiko.PKey: ロードされたプライベートキーオブジェクト。
        
        Raises:
            SSHClientError: サポートされていない鍵形式の場合。
        """
        key_types = [
            paramiko.RSAKey,
            paramiko.DSSKey,
            paramiko.ECDSAKey,
            paramiko.Ed25519Key
        ]
        key_file = io.StringIO(self.key_str)
        for key_type in key_types:
            try:
                return key_type.from_private_key(key_file)
            except paramiko.SSHException:
                key_file.seek(0)  # ファイルポインタを先頭に戻す
                continue
        raise SSHClientError("サポートされていない鍵形式です。")

    def connect(self):
        """SSH接続を確立する。成功するまでリトライする。"""
        while True:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                pkey = self._load_private_key()
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=pkey,
                    timeout=self.timeout
                )
                self.client.get_transport().set_keepalive(10)

                # 接続に成功したらループを抜ける
                print(f"Successfully connected to {self.host}")
                break
            except AuthenticationException as e:
                raise SSHAuthenticationError(f"SSH認証に失敗しました: {e}") from e
            except (NoValidConnectionsError, SSHException) as e:
                print(f"SSH接続に失敗しました: {e}. リトライします...")
                time.sleep(self.retry_delay)
            except Exception as e:
                print(f"予期しないエラーが発生しました: {e}. リトライします...")
                time.sleep(self.retry_delay)

    def disconnect(self):
        """SSH接続を切断する。"""
        if self.client:
            self.client.close()
            self.client = None

    def cmd(self, command: str) -> str:
        """
        リモートインスタンス上でコマンドを実行し、標準出力を返す。
        
        Args:
            command (str): 実行するコマンド。
        
        Returns:
            str: コマンドの標準出力。
        
        Raises:
            SSHCommandError: コマンドの実行に失敗した場合。
            SSHClientError: SSH接続が確立されていない場合。
        """
        if not self.client:
            raise SSHClientError("SSH接続が確立されていません。'connect()' を呼び出してください。")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8').strip()
            error_output = stderr.read().decode('utf-8').strip()
            
            if exit_status != 0:
                raise SSHCommandError(command, exit_status, output, error_output)
            
            return output
        except SSHException as e:
            raise SSHClientError(f"コマンド実行中にエラーが発生しました: {e}") from e

    def get_ssh_login_command(self) -> str:
        """
        SSHログイン用のワンライナーコマンドを生成します。
        このコマンドは秘密鍵を一時ファイルに書き出し、SSH接続を行い、
        接続終了後に一時ファイルを削除します。
        
        Returns:
            str: ワンライナーのSSHログインコマンド。
        """
        # 一時鍵ファイルのパス
        key_file_path = "/tmp/temp_key.pem"
        
        # SSHオプションの設定
        server_alive_interval = 10       # 秒単位での間隔
        server_alive_count_max = 3       # 最大カウント数
        
        # SSHログインコマンドの生成
        ssh_command = (
            f'echo -e "{self.key_str}" > {key_file_path} && '
            f'chmod 600 {key_file_path} && '
            f'ssh -i {key_file_path} -p {self.port} '
            f'-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
            f'-o ServerAliveInterval={server_alive_interval} '
            f'-o ServerAliveCountMax={server_alive_count_max} '
            f'{self.username}@{self.host} && '
            f'rm -f {key_file_path}'
        )
        
        return ssh_command

def convert_to_oneline_echo(file_path, output_file):
    """
    指定されたファイルの内容を1行の echo コマンドに変換して出力します。

    Args:
        file_path (str): テキストファイルのパス。
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    # 各行を結合し、改行文字を含む形に変換
    oneline_command = 'echo -e "' + ''.join([line.rstrip() + '\\n' for line in lines]) + '"' + f"> {output_file}"
    return oneline_command
                