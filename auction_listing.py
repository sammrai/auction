import os, fcntl, schedule, time, argparse
from lib.auction import get_original_files, logger, YahooAuctionTrade
from lib.image_filters import process_images

LOCKFILE = "/tmp/daily_task.lock"

def daily_task(accounts):
    process_images(get_original_files(), override=False)
    for account in accounts:
        logger.info(f"Processing account: {account}")
        YahooAuctionTrade(account).listing_auto()

def ensure_single_instance():
    lock_file = open(LOCKFILE, "w")  # ロックファイルを開く
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)  # 排他ロックを取得
        return lock_file  # ファイル記述子を返して保持
    except IOError:
        logger.error("Another instance of this script is already running.")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("accounts", nargs="+", help="List of account names.")
    args = parser.parse_args()
    
    lock_file = ensure_single_instance()  # ロック取得
    schedule.every().day.at("00:00").do(daily_task, accounts=args.accounts)
    logger.info("Scheduler started. Waiting for tasks...")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        lock_file.close()  # スクリプト終了時にロック解除
