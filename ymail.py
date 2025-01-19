import imaplib
import email
from email.header import decode_header
import re
import time
from dataclasses import dataclass, field
from email.message import Message
from typing import List, Optional
import fcntl

def safe_decode(value):
    """安全にデコードする関数"""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value

@dataclass
class Attachment:
    filename: str
    content_type: str
    size: int

@dataclass
class MailMessage:
    uid: int
    subject: str
    from_: str
    to: str
    date: str
    message_id: str
    cc: Optional[str] = ""
    body: str = ""
    attachments: List[Attachment] = field(default_factory=list)

    @staticmethod
    def from_email_message(uid: int, msg: Message) -> 'MailMessage':
        """
        email.message.Message オブジェクトから MailMessage インスタンスを作成する。
        ここでは本文や添付ファイルはまだ取得しない。
        """
        subject_decoded = decode_mime_header(msg.get("Subject"))
        from_decoded = decode_mime_header(msg.get("From"))
        to_decoded = decode_mime_header(msg.get("To"))
        date_decoded = decode_mime_header(msg.get("Date"))
        message_id_decoded = decode_mime_header(msg.get("Message-ID"))
        cc_decoded = decode_mime_header(msg.get("Cc"))

        return MailMessage(
            uid=uid,
            subject=subject_decoded,
            from_=from_decoded,
            to=to_decoded,
            date=date_decoded,
            message_id=message_id_decoded,
            cc=cc_decoded
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
                decoded_parts.append(part.decode("utf-8", errors="ignore"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)

def get_text_body(msg) -> str:
    """
    メールオブジェクトから text/plain の本文をすべて連結して返す。
    """
    if not msg.is_multipart():
        payload = msg.get_payload(decode=True)
        return payload.decode("utf-8", errors="ignore") if payload else ""

    body_parts = []
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode("utf-8", errors="ignore"))
    return "".join(body_parts)

def get_attachments(msg) -> List[Attachment]:
    """
    メールオブジェクトから添付ファイル情報を抽出してリストで返す。
    """
    attachments = []
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            filename = decode_mime_header(part.get_filename())
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            attachments.append(Attachment(filename=filename, content_type=content_type, size=size))
    return attachments

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
        poll_interval: int = 60,
        mailbox: str = "INBOX",
    ):
        self.email_address = email_address
        self.password = password
        self.server = server
        self.port = port
        self.poll_interval = poll_interval
        self.mail = None
        self.last_uid = 0
        self.callbacks = []
        self.mailbox = mailbox

    def connect(self):
        """IMAP サーバーに接続して認証を行う。"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.server, self.port)
            self.mail.login(self.email_address, self.password)
            self.mail.select(self.mailbox)
        except Exception as e:
            print(f"Connection failed: {e}")
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

    def fetch_new_messages(self) -> List[MailMessage]:
        """
        前回取得した最大 UID (self.last_uid) より新しいメールを取得し、
        (ヘッダだけ埋まった) MailMessage のリストを返す。
        """
        if not self.mail:
            return []
        self.connect()
        if not self.mail:
            return []
        criteria = f"UID {self.last_uid + 1}:*"
        typ, data = self.mail.uid('search', None, criteria)
        if typ != "OK" or not data or not data[0]:
            return []

        new_uids = data[0].split()  # [b'102', b'103', ...]
        new_messages = []
        for uid_bytes in new_uids:
            uid = int(uid_bytes)
            if uid <= self.last_uid:
                continue

            # ヘッダだけ取得
            typ2, msg_data = self.mail.uid('fetch', str(uid), '(BODY.PEEK[HEADER])')
            if typ2 == "OK":
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_email = response_part[1]
                        msg = email.message_from_bytes(raw_email)
                        mail_msg = MailMessage.from_email_message(uid, msg)
                        new_messages.append(mail_msg)

        return new_messages

    def fetch_body_and_attachments(self, uid: int, mail_msg: MailMessage):
        """
        指定した UID のメール本文と添付ファイル情報を取得して MailMessage に設定する。
        """
        if not self.mail:
            self.connect()
            if not self.mail:
                return

        typ, msg_data = self.mail.uid('fetch', str(uid), '(RFC822)')
        if typ == 'OK' and msg_data:
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email = response_part[1]
                    msg = email.message_from_bytes(raw_email)
                    mail_msg.body = get_text_body(msg)
                    mail_msg.attachments = get_attachments(msg)
                    break

    def register_callback(
        self,
        from_pattern: str = None,
        subject_pattern: str = None,
        body_pattern: str = None,
        callback=None
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
        条件にマッチしたら本文と添付ファイルを取得したうえでコールバックを呼ぶ (本文つきの MailMessage を渡す)。
        
        ※ ここがポイント:
          - body_pattern がある場合は本文をチェック
          - body_pattern が「ない」場合も自動的に本文マッチとみなし、本文を取得してコールバックに渡す。
        """
        new_msgs = self.fetch_new_messages()
        max_uid_in_batch = self.last_uid

        for mail_msg in new_msgs:
            body_fetched = False  # このメールの本文はまだ取得していない

            for cb in self.callbacks:
                # 1) FROM が指定＆マッチするか
                if cb['from_regex'] and not cb['from_regex'].search(mail_msg.from_):
                    continue

                # 2) SUBJECT が指定＆マッチするか
                if cb['subject_regex'] and not cb['subject_regex'].search(mail_msg.subject):
                    continue

                # 3) body_pattern があるかないかで分岐
                #    - ある → 本文を fetch してパターンマッチを確認
                #    - ない → 自動的にマッチ扱いだが、callback に本文つき MailMessage を渡す必要があるので、本文を fetch
                if cb['body_regex'] is not None:
                    # body_pattern が存在する → チェックする
                    if not body_fetched:
                        self.fetch_body_and_attachments(mail_msg.uid, mail_msg)
                        body_fetched = True

                    if not cb['body_regex'].search(mail_msg.body):
                        continue  # 本文マッチしないので次の callback へ
                else:
                    # body_pattern が存在しない → 自動的に本文マッチ扱い
                    if not body_fetched:
                        self.fetch_body_and_attachments(mail_msg.uid, mail_msg)
                        body_fetched = True

                # ここまで来たら「すべての条件」をクリア
                if cb['callback']:
                    cb['callback'](mail_msg)

            if mail_msg.uid > max_uid_in_batch:
                max_uid_in_batch = mail_msg.uid

        if max_uid_in_batch > self.last_uid:
            self.last_uid = max_uid_in_batch


    def run(self, include_last_n=0):
        """ロックを取得してから実行する。"""
        lock_file_path = '/tmp/mail_checker.lock'  # ロックファイルのパス
        lock_file = open(lock_file_path, 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)  # ロックを取得
        except IOError:
            raise Exception("Another instance is already running.")

        self.connect()
        if not self.mail:
            return
        current_max_uid = self._get_current_max_uid()
        self.last_uid = max(0, current_max_uid - include_last_n)

        try:
            while True:
                try:
                    self.check_and_run_callback()
                except imaplib.IMAP4.abort:
                    # 接続切れをリカバリ
                    self.close()
                    time.sleep(5)
                    self.connect()
                    if not self.mail:
                        break
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()
            fcntl.flock(lock_file, fcntl.LOCK_UN)  # ロックを解放
            lock_file.close()