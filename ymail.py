import imaplib
import email
from email.header import decode_header
import re
import time
from dataclasses import dataclass
from email.message import Message

# from lib.auction import initialize_logger
# logger = initialize_logger(log_file="mail.log")


def safe_decode(value):
    """安全にデコードする関数"""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


@dataclass
class MailMessage:
    uid: int
    subject: str
    from_: str
    body: str

    @staticmethod
    def from_email_message(uid: int, msg: Message) -> 'MailMessage':
        """
        email.message.Message オブジェクトから MailMessage インスタンスを作成する。
        """
        subject_decoded = decode_mime_header(msg.get("Subject"))
        from_decoded = decode_mime_header(msg.get("From"))
        body_text = get_text_body(msg)

        return MailMessage(
            uid=uid,
            subject=subject_decoded,
            from_=from_decoded,
            body=body_text
        )


def decode_mime_header(header_value: str) -> str:
    """
    MIME エンコード(= ?UTF-8?Q?... など)されたヘッダを
    正しくデコードして結合した文字列を返す。
    """
    if not header_value:
        return ""
    decoded_parts = []
    for part, enc in decode_header(header_value):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(enc or "utf-8", errors="ignore"))
            except:
                decoded_parts.append(part.decode("utf-8", errors="ignore"))  # フォールバック
        else:
            # part は str の場合
            decoded_parts.append(part)
    return "".join(decoded_parts)


def get_text_body(msg) -> str:
    """
    メールオブジェクトから text/plain の本文をすべて連結して返す。
    マルチパートの場合に複数パートがある場合も想定。
    """
    if not msg.is_multipart():
        # シンプルなメールの場合
        payload = msg.get_payload(decode=True)
        return payload.decode("utf-8", errors="ignore") if payload else ""

    # マルチパートの場合
    body_parts = []
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode("utf-8", errors="ignore"))
    return "".join(body_parts)


class IMAPNewMailCheckerByUID:
    """
    UID ベースで“新規”メールだけを定期的に取得し、正規表現フィルタがヒットしたら
    コールバックを実行するクラス。
    既読フラグは変更しないため、何度も同じメールがヒットすることがありません。
    """

    def __init__(
        self,
        email_address: str,
        password: str,
        server: str = "imap.mail.yahoo.co.jp",
        port: int = 993,
        poll_interval: int = 60
    ):
        """
        :param email_address: ログインに使用するメールアドレス
        :param password: ログインに使用するパスワード (アプリパスワード推奨)
        :param server: IMAP サーバーのアドレス (Yahooなら 'imap.mail.yahoo.co.jp')
        :param port: IMAP サーバーのポート (既定: 993)
        :param poll_interval: ポーリングでチェックする間隔 (秒)
        """
        self.email_address = email_address
        self.password = password
        self.server = server
        self.port = port
        self.poll_interval = poll_interval

        self.mail = None  # imaplib.IMAP4_SSL のインスタンス

        # これより大きい UID のメールだけを検索する
        self.last_uid = 0  # まだ取得していない場合は 0 にしておく

        self.callbacks = []  # 登録されたコールバックを保持するリスト

    def connect(self):
        """IMAP サーバーに接続して認証を行う。"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.server, self.port)
            self.mail.login(self.email_address, self.password)
            self.mail.select("INBOX")
            # logger.debug("IMAPサーバーに接続しました。")

        except Exception as e:
            # logger.debug(f"IMAP接続中にエラーが発生しました: {e}")
            self.mail = None

    def close(self):
        """IMAP セッションを閉じる。"""
        if self.mail:
            try:
                self.mail.close()
            except:
                pass
            try:
                self.mail.logout()
            except:
                pass
            self.mail = None
            # logger.debug("IMAPサーバーから切断しました。")

    def _get_current_max_uid(self) -> int:
        """
        INBOX 内の最大 UID を取得して返す。
        """
        typ, data = self.mail.uid('search', None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return 0
        uid_list = data[0].split()  # [b'1', b'2', ...]
        int_uids = [int(x) for x in uid_list]
        return max(int_uids) if int_uids else 0

    def fetch_new_messages(self):
        """
        前回取得した最大 UID (self.last_uid) より新しいメールを取得し、
        (msg_uid, Messageオブジェクト) のリストを返す。
        """
        if not self.mail:
            return []
        self.connect()
        criteria = f"UID {self.last_uid}:*"
        # logger.debug(f"検索クエリ: {criteria}")
        typ, data = self.mail.uid('search', None, criteria)
        if typ != "OK" or not data or not data[0]:
            return []

        new_uids = data[0].split()  # [b'102', b'103', ...]
        new_messages = []

        for uid_bytes in new_uids:
            uid = int(uid_bytes)
            if uid <= self.last_uid:
                continue
            # メール本体取得 (RFC822 は本文も含め全体を取得)
            typ2, msg_data = self.mail.uid('fetch', uid_bytes, '(RFC822)')
            if typ2 == "OK":
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_email = response_part[1]
                        msg = email.message_from_bytes(raw_email)
                        new_messages.append(MailMessage.from_email_message(uid, msg))

        return new_messages

    def register_callback(
        self,
        from_pattern: str = None,
        subject_pattern: str = None,
        body_pattern: str = None,
        callback = None
    ):
        """
        新しいコールバックを登録する。
        :param from_pattern: 送信元の正規表現パターン (str または None)
        :param subject_pattern: 件名の正規表現パターン (str または None)
        :param body_pattern: 本文の正規表現パターン (str または None)
        :param callback: 条件にマッチした場合に実行するコールバック関数
        """
        from_regex = re.compile(from_pattern, re.IGNORECASE) if from_pattern else None
        subject_regex = re.compile(subject_pattern, re.IGNORECASE) if subject_pattern else None
        body_regex = re.compile(body_pattern, re.IGNORECASE) if body_pattern else None

        self.callbacks.append({
            'from_regex': from_regex,
            'subject_regex': subject_regex,
            'body_regex': body_regex,
            'callback': callback
        })

    def check_and_run_callback(self):
        """
        新しいメール(UIDベース)を取得し、登録されたすべてのコールバック条件に対してチェックし、
        条件にマッチしたら対応するコールバックを呼ぶ。
        """
        new_msgs = self.fetch_new_messages()
        max_uid_in_batch = self.last_uid  # 今回取得した中で最も大きい UID を確認するための変数
        # logger.debug(f"last UID: {self.last_uid}")

        for mail_msg in new_msgs:
            # 各登録されたコールバックに対してチェック
            for cb in self.callbacks:
                if self._match_all(
                    cb['from_regex'],
                    cb['subject_regex'],
                    cb['body_regex'],
                    mail_msg.from_,
                    mail_msg.subject,
                    mail_msg.body
                ):
                    if cb['callback']:
                        cb['callback'](mail_msg)

            if mail_msg.uid > max_uid_in_batch:
                max_uid_in_batch = mail_msg.uid

        # 今回取得したメールの中で最大の UID を記録し、次回以降に重複取得しないようにする
        if max_uid_in_batch > self.last_uid:
            self.last_uid = max_uid_in_batch
            # logger.debug(f"次の検索UID: {self.last_uid}")


    @staticmethod
    def _match_all(from_regex, subject_regex, body_regex, from_, subject, body):
        """
        送信元、件名、本文に対応する正規表現が None でなければ検索し、
        すべてマッチしたら True を返す。
        """
        if from_regex and not from_regex.search(from_):
            return False
        if subject_regex and not subject_regex.search(subject):
            return False
        if body_regex and not body_regex.search(body):
            return False
        return True

    def run(self, include_last_n=0):
        """
        登録されたすべてのコールバックを処理する。
        :param include_last_n: 初回に含める最後のN件のメール
        """
        self.connect()

        # 初回の最大 UID を取得
        self.last_uid = self._get_current_max_uid() - include_last_n
        # logger.debug(f"max uid: {self.last_uid}")

        if not self.mail:
            # logger.error("接続に失敗したため、終了します。")
            return

        # logger.info("=== ポーリング開始 (UID ベースで最新メールのみ取得) ===")
        try:
            while True:
                try:
                    self.check_and_run_callback()
                except imaplib.IMAP4.abort as e:
                    # logger.error(f"IMAP セッションが切断されました: {e}")
                    # 一旦クローズして再度接続を試みる
                    self.close()
                    time.sleep(5)
                    self.connect()
                    if not self.mail:
                        # logger.error("再接続に失敗したため終了します。")
                        break
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            # logger.error("\nユーザが中断しました。")
            pass

        finally:
            self.close()
            # logger.debug("=== ポーリング終了 ===")

