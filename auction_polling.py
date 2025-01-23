from lib.ymail import IMAPNewMailCheckerByUID
from lib.auction import YahooAuctionTrade, logger, get_original_files_with_tags, get_file_exclude
import re
from lib.auction import register_db
from lib.influxdb import client
from datetime import datetime
import time
import sys
import argparse

# 引数を解析
parser = argparse.ArgumentParser(description="Yahoo Auction Mail Checker")
parser.add_argument("account", help="Yahooアカウント")
parser.add_argument("-n", type=int, default=0, help="include_last_n の指定 (デフォルトは0)")
args = parser.parse_args()

account = args.account
include_last_n = args.n

yat = YahooAuctionTrade(account)
EMAIL = yat.account_config["email"]
PASSWORD = yat.account_config["password"]

checker = IMAPNewMailCheckerByUID(
    email_address=EMAIL,
    password=PASSWORD,
    poll_interval=600,
    mailbox="yahoo_auction_callback",
)

def on_test(mail_msg):
    logger.info(f"{account} ==== テスト ====")
    logger.info(f"{account} UID: {mail_msg.uid}")
    logger.info(f"{account} 件名: {mail_msg.subject}")
    logger.info(f"{account} date: {mail_msg.date}")
    logger.info(f"{account} test start")
    time.sleep(10)
    logger.info(f"{account} test complete")

checker.register_callback(
    callback=on_test
)

def on_filter_matched_auction(mail_msg):
    logger.info(f"{account} ==== 支払い完了 ====")
    logger.info(f"{account} UID: {mail_msg.uid}")
    logger.info(f"{account} 件名: {mail_msg.subject}")
    logger.info(f"{account} date: {mail_msg.date}")
    
    file_paths = get_original_files_with_tags(yat.tags, suffix="submission", drop_missing=True)
    assert file_paths != 0
    if account == "shunn_wanda":
        gift_image_candidates = [i for i in get_file_exclude(file_paths) if "items/c" in i]
        assert len(gift_image_candidates) > 20
    else:
        gift_image_candidates = None

    ret = yat.ship(gift_image_candidates)
    df = yat.get_sales(datetime.now().strftime("%Y%m"))
    register_db(client, df)

checker.register_callback(
    subject_pattern=r'支払いが完了しました',
    from_pattern = r'^auction-master@mail\.yahoo\.co\.jp$',
    callback=on_filter_matched_auction
)

def extract_links_from_body(mail_body: str):
    pattern = r'https://contact\.auctions\.yahoo\.co\.jp/seller/[^ \n]*'
    links = re.findall(pattern, mail_body)
    return links

def on_matome(mail_msg):
    logger.info(f"{account} ==== まとめ取引 ====")
    urls = extract_links_from_body(mail_msg.body)
    assert len(urls)==1, mail_msg.body
    ret = yat.accept_omatome(urls[0])

checker.register_callback(
    subject_pattern=r'まとめ依頼',
    from_pattern = r'^auction-master@mail\.yahoo\.co\.jp$',
    # body_pattern = "yahoo",
    callback=on_matome
)

import traceback

def mail_polling():
    logger.info(f"{account} ポーリング開始 (include_last_n={include_last_n})")
    try:
        checker.run(include_last_n=include_last_n)
    except Exception as e:
        # 例外発生時のログ出力
        logger.error("ポーリング中に例外が発生しました:\n" + traceback.format_exc())
        return

mail_polling()
logger.info(f"{account} ポーリングを終了しました")


# PYTHONPATH=. nohup python lib/auction_polling.py shunn_wanda -n 4 &
# PYTHONPATH=. nohup python lib/auction_polling.py yeqzz34475 -n 1&