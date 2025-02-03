import requests
import os
import functools
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from requests import PreparedRequest
import schedule, time
from tqdm import tqdm
import re
from dotenv import load_dotenv

load_dotenv()

class ProxySession:
    def __init__(self, proxy_host="192.168.32.70", proxy_port=8901, cookies=None):
        self.session = requests.Session()
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        self.proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
        
        # クッキーをセット
        if cookies:
            for cookie in cookies.split("; "):  # "key=value" の形式を解析
                key, value = cookie.split("=", 1)
                self.session.cookies.set(key, value)

    def get(self, url, use_proxy=True, **kwargs):
        if "proxies" in kwargs:
            raise ValueError("Proxies cannot be overridden in this session.")
        if use_proxy:
            kwargs["proxies"] = self.proxies
        return self.session.get(url, **kwargs)

    def post(self, url, use_proxy=True, **kwargs):
        if "proxies" in kwargs:
            raise ValueError("Proxies cannot be overridden in this session.")
        if use_proxy:
            kwargs["proxies"] = self.proxies
        return self.session.post(url, **kwargs)

def login_letao(proxy_session):
    url = "https://www.letao.com.tw/config/login.php"
    
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "ja,en-US;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.letao.com.tw",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "referer": "https://www.letao.com.tw/config/login.php",
        "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    }

    data = {
        "done": "",
        "email": os.environ.get("LETAO_EMAIL"),
        "passwd": os.environ.get("LETAO_PASSWORD"),
    }
    
    response = proxy_session.post(url, headers=headers, data=data, use_proxy=False)
    assert response.status_code == 200
    assert "帳號或密碼無效，請重新輸入。" not in response.text, "password invalid"
    return response


def parse_price(price_str):
    """価格文字列から整数を抽出"""
    if price_str:
        return int(price_str.replace('円', '').replace(',', '').strip())
    return None

def parse_end_time(end_time_str):
    """end_time文字列をdatetime型に変換"""
    if not end_time_str:
        return None
    try:
        # 現在の年を基準にする
        current_year = 2025
        month_day, time_part = end_time_str.split(' ')
        month, day = map(int, month_day.split('/'))
        hour, minute = map(int, time_part.split(':'))
        
        # 1月1日以降なら2025年、それ以外は2024年
        if (month, day) >= (1, 1):
            year = 2025
        else:
            year = 2024
        
        return datetime(year, month, day, hour, minute)
    except Exception as e:
        print(f"end_timeのパースに失敗しました: {end_time_str} ({e})")
        return None



@functools.cache
def get_products_yahoo(proxy_session, begin, query, num=100):
    data = []
    
    url = "https://auctions.yahoo.co.jp/closedsearch/closedsearch"
    params = {
        "p": query,
        "va": query,
        "b": begin,
        "n": num
    }
    
    # リクエスト送信
    response = proxy_session.get(url, params=params)
    html = response.text
    
    soup = BeautifulSoup(html, "html.parser")
    
    # すべてのProductクラスを持つliタグを取得
    for product in soup.find_all("li", class_="Product"):
        product_data = {}
        
        # 商品タイトルとリンク
        title_tag = product.find("h3", class_="Product__title")
        if title_tag:
            product_data["title"] = title_tag.get_text(strip=True)
            product_data["url"] = title_tag.a["href"] if title_tag.a else None
        product_data["id"] = product_data["url"].split("/")[-1]
        # 画像リンク
        image_tag = product.find("img", class_="Product__imageData")
        if image_tag:
            product_data["image_url"] = image_tag.get("src", None)
        
        # 価格と開始価格
        price_tag = product.find("span", class_="Product__priceValue")
        if price_tag:
            product_data["final_price"] = parse_price(price_tag.get_text())
        start_price_tag = product.find("span", class_="Product__priceValue--start")
        if start_price_tag:
            product_data["start_price"] = parse_price(start_price_tag.get_text())
        
       # カテゴリID
        category_links = product.find_all("a", class_="Product__categoryLink")
        if category_links:
            # 最後のカテゴリIDを取得
            last_category = category_links[-1]["href"]
            product_data["category_id"] = int(last_category.split("/")[-2])
    
        
        # 入札数と終了日時
        other_info = product.find("dl", class_="Product__otherInfo")
        if other_info:
            dd_tags = other_info.find_all("dd")
            bids = other_info.find("a", class_="Product__bid")
            if bids is not None:
               product_data["bids"] = int(bids.get_text(strip=True))
            else:
                product_data["bids"] = None
            product_data["end_time"] = parse_end_time(other_info.find("span", class_="Product__time").get_text(strip=True))
        # else:
            # product_data["bids"] = None
            # product_data["end_time"] = None
        
        # 出品者情報
        seller_tag = product.find("div", class_="Product__sellerName")
        if seller_tag:
            seller_link = seller_tag.find("a")
            if seller_link and seller_link.get("href"):
                product_data["seller"] = seller_link["href"].rstrip('/').split('/')[-1]
                # product_data["seller_url"] = seller_link["href"]
            else:
                product_data["seller"] = None
                # product_data["seller_url"] = None
        else:
            product_data["seller"] = None
            # product_data["seller_url"] = None
        
        # データを追加
        data.append(product_data)

    
    # Pandasデータフレームに変換
    df = pd.DataFrame(data)
    assert len(df)==num, (url, params, len(df), num)
    df = df.set_index("id")
    # データ型の変換
    df['final_price'] = df['final_price'].astype('Int64')  # NaNを許容する整数型
    df['start_price'] = df['start_price'].astype('Int64')  # NaNを許容する整数型
    df['end_time'] = pd.to_datetime(df['end_time'])
    return df

    

# get_products_yahoo(1,"アート")

@functools.cache
def get_products_letao(proxy_session, begin, query, num=50):
    """
    Letao のオークション履歴ページから取引データを取得する関数。
    
    引数:
      begin: Yahoo!版と同様、取得開始件数（1件目の場合 begin=1）。
             Letao ページは 1 ページあたり num 件として、ページ番号 = ((begin-1)//num)+1 で取得。
      query: 検索クエリ（例："アート"）
      num:  1 ページあたりの表示件数（例: 100）
    
    戻り値:
      取得した取引情報を格納した Pandas DataFrame
      （各行の index は取引ID。カラムは title, url, image_url, final_price, start_price, bids, end_time, seller など）
    """
    # Letao 版はページ番号で取得するため、begin からページ番号を算出
    page = ((begin - 1) // num) + 1
    base_url = "https://www.letao.com.tw/yahoojp/auctions/history.php"
    
    # 以下は Letao サイト用のパラメータ例（必要に応じて調整してください）
    params = {
        "sortorder": "endLH",
        "price_type": "",
        "minprice": "",
        "maxprice": "",
        "istatus": "",
        "abatch": "",
        "fixed": "",
        "new": "",
        "p": query,
        "category": "",      # 必要に応じてカテゴリID（例: "26146"）を設定するか空文字
        "seller": "",
        "sp": "",
        "stype": "0",
        "adult": "1",
        "fuzzy": "",
        "page": page,
        "viewcount": num   # 1 ページあたりの表示件数
    }
    req = PreparedRequest()
    req.prepare_url(base_url, params)
    generated_url = req.url

    response = proxy_session.get(base_url, params=params)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    
    data = []
    # Letao 版では、各取引は <div class="item"> 要素内にある
    items = soup.find_all("div", class_="item")
    for item in items:
        product_data = {}
        
        # --- 取引IDの取得 ---
        # 多くの場合、<div class="imgInfo"> 内の <img> タグに data-item 属性が設定されている
        img_info = item.find("div", class_="imgInfo")
        if img_info:
            a_tag = img_info.find("a")
            if a_tag:
                img_tag = a_tag.find("img")
                if img_tag and img_tag.has_attr("data-item"):
                    product_data["id"] = img_tag["data-item"]
                else:
                    # もし data-item 属性がない場合は、リンク URL のクエリ文字列から aID を抽出する
                    href = a_tag.get("href")
                    if href:
                        # href が "//www.letao.com.tw/..." の場合は https: を補完
                        if not href.startswith("http"):
                            href = "https:" + href
                        parsed = urlparse.urlparse(href)
                        qs = urlparse.parse_qs(parsed.query)
                        if "aID" in qs:
                            product_data["id"] = qs["aID"][0]
        # ID が取得できなければそのアイテムはスキップ
        if "id" not in product_data:
            continue
        
        # --- タイトルとリンク ---
        title_info = item.find("div", class_="titleInfo")
        if title_info:
            title_div = title_info.find("div", class_="title")
            if title_div:
                a_tag = title_div.find("a")
                if a_tag:
                    product_data["title"] = a_tag.get_text(strip=True)
                    href = a_tag.get("href")
                    if href:
                        if href.startswith("//"):
                            href = "https:" + href
                        product_data["url"] = href

        # --- 画像リンク ---
        if img_info:
            img_tag = img_info.find("img")
            if img_tag:
                product_data["image_url"] = img_tag.get("src", None)
        
        # --- 価格情報 ---
        # Letao 版では、1 ページ内に複数の <div class="priceInfo"> があり、
        # 最初のものが「結標價」（最終落札価格）、2 番目が「買」価格（開始価格）とする例
        price_info_divs = item.find_all("div", class_="priceInfo")
        if len(price_info_divs) > 0:
            mp_div = price_info_divs[0].find("div", class_="mp")
            if mp_div:
                product_data["final_price"] = parse_price(mp_div.get_text())
        if len(price_info_divs) > 1:
            mp_div = price_info_divs[1].find("div", class_="mp")
            if mp_div:
                product_data["start_price"] = parse_price(mp_div.get_text())
        else:
            product_data["start_price"] = None
        product_data["category_id"] = 26146
        # --- 入札数 ---
        bids_div = item.find("div", class_="bidsInfo")
        if bids_div:
            try:
                product_data["bids"] = int(bids_div.get_text(strip=True))
            except:
                product_data["bids"] = None
        
        # --- 終了日時 ---
        time_div = item.find("div", class_="timeInfo")
        if time_div:
            product_data["end_time"] = parse_end_time(time_div.get_text(strip=True))
        
        # --- 出品者 ---
        # タイトル情報内の <div class="info"> 内に、<div class="seller">（または "seller m"）がある場合
        if title_info:
            seller_div = title_info.find("div", class_="seller")
            if seller_div:
                a_tag = seller_div.find("a")
                if a_tag:
                    product_data["seller"] = a_tag.get_text(strip=True)
        
        data.append(product_data)
    
    # DataFrame に変換
    df = pd.DataFrame(data)
    generate_url = lambda url: (
        f"https://page.auctions.yahoo.co.jp/jp/auction/{match.group(1)}"
        if (match := re.search(r'aID=([\w]+)', url)) else None
    )
    if df.empty:
        title_tag = soup.find("div", class_="title")
        print(title_tag)
        print(generated_url)
        return df
    df["url"] = df["url"].apply(generate_url)
    df = df.set_index("id")
    df['final_price'] = df['final_price'].astype('Int64')
    df['start_price'] = df['start_price'].astype('Int64')
    df['end_time'] = pd.to_datetime(df['end_time'])
    return df


def fetch_all_products_with_cache(proxy_session, query, adult=False, total_items=15000, batch_size=50, cache_dir="cache_trade"):
    """
    指定されたクエリに対して、最新データ（1ページ目から）を順次取得し、
    キャッシュ済みのIDに到達したら以降のページ取得を打ち切る。
    
    キャッシュは1クエリにつき1つの.pklファイルとして保存するため、毎回新規データのみが追加されます。
    
    Args:
        query (str): 検索クエリ
        total_items (int): 検索可能な最大件数（初期値15000）
        batch_size (int): 1回のリクエストで取得する件数（初期値100）
        cache_dir (str): キャッシュファイルの保存ディレクトリ（初期値"cache_trade"）
    
    Returns:
        pd.DataFrame: 取得した取引データ（キャッシュ済みデータと新規データの結合）
    """
    # キャッシュディレクトリがなければ作成
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    # クエリ中の空白をアンダースコアに変換してファイル名とする
    sanitized_query = query.replace(" ", "_")
    if adult: sanitized_query = "a_"+sanitized_query
    cache_file = os.path.join(cache_dir, f"{sanitized_query}.pkl")
    
    # 既存キャッシュの読み込み（なければ空のDataFrame）
    if os.path.exists(cache_file):
        cached_df = pd.read_pickle(cache_file)
        cached_df['end_time'] = pd.to_datetime(cached_df['end_time'], errors='coerce')
    else:
        cached_df = pd.DataFrame()
        cached_df.index.name = "id"
    
    cached_ids = set(cached_df.index) if not cached_df.empty else set()
    new_dfs = []
    
    total_pages = (total_items + batch_size - 1) // batch_size
    pbar = tqdm(range(1, total_items + 1, batch_size), total=total_pages, desc=f"【{query}】", unit="page")
    
    for start in pbar:
        if adult:
            df_page = get_products_letao(proxy_session, start, query, num=batch_size)
        else:
            df_page = get_products_yahoo(proxy_session, start, query, num=batch_size)
            
        if df_page.empty:
            break
        
        rows_to_add = []
        for idx in df_page.index:
            if idx in cached_ids:
                # キャッシュ済みの取引に到達したため、これ以降のデータは古いと判断
                break
            rows_to_add.append(idx)
        
        if rows_to_add:
            new_page_df = df_page.loc[rows_to_add]
            new_dfs.append(new_page_df)
        # ページ内で途中からキャッシュ済みのIDに到達した場合、以降のページは取得不要と判断
        if len(rows_to_add) < len(df_page):
            tqdm.write(f"キャッシュ済みの取引に到達したため、これ以降のページ取得を打ち切ります。")
            break
        
        # 現在までに取得した新規データの最新終了日時をプログレスバーに表示
        if new_dfs:
            combined_new = pd.concat(new_dfs)
            oldest_dt = combined_new['end_time'].min()
            pbar.set_postfix(oldest=oldest_dt.strftime("%Y-%m-%d %H:%M") if pd.notnull(oldest_dt) else None)
    
    # 新規データとキャッシュ済みデータを結合（新規データを優先）
    if new_dfs:
        new_data = pd.concat(new_dfs)
        combined_df = pd.concat([new_data, cached_df])
        combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    else:
        new_data = pd.DataFrame()
        combined_df = cached_df
    
    # キャッシュ更新（.pkl形式で保存）
    combined_df.to_pickle(cache_file)
    
    # 最終的な最新終了日時を表示
    if not combined_df.empty:
        final_latest = combined_df['end_time'].max()
        print(f"[{query}] 最新の終了日時: {final_latest} 追加取得件数: {len(new_data)}")
    else:
        print(f"[{query}] データは取得されませんでした。")
    
    return combined_df

# ---------------------------
# 複数クエリ実行用関数
# ---------------------------
def query_word(proxy_session, queries, adult=False):
    """
    複数のクエリに対して取引データを取得し、重複を除いた上で終了日時順にソートして返す。
    
    Args:
        queries (list of str): 検索クエリのリスト
    
    Returns:
        pd.DataFrame: 全クエリの結合結果
    """
    dfs = []
    for query in queries:
        df = fetch_all_products_with_cache(proxy_session, query, total_items=15000, batch_size=50, cache_dir="cache_trade", adult=adult)
        dfs.append(df)
    final_df = pd.concat(dfs)
    final_df = final_df[~final_df.index.duplicated(keep='first')]
    final_df = final_df.sort_values("end_time")
    return final_df


def daily_task():
    proxy_session = ProxySession()
    response = proxy_session.get("https://ipinfo.io")
    print(response.json())
    assert response.status_code==200

    ret = login_letao(proxy_session)
    for adult in [True, False]:
        print("処理開始", adult)
        queries = [
            "アート ポスター",
            "アート イラスト",
            "ポスター",
            "A4",
            "AI",
        ]
        df = query_word(proxy_session, queries, adult=adult)
        df['adult'] = adult
        print(f"総件数: {len(df)}")


if __name__ == "__main__":
    daily_task()
    # schedule.every().day.at("00:00").do(daily_task)
    # print("start daily task...")
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
