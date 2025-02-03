from tqdm import tqdm
import re
def fetch_all_products_with_cache(query, adult=False, total_items=15000, batch_size=50, cache_dir="cache_trade"):
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
            df_page = get_products_letao(start, query, num=batch_size)
        else:
            df_page = get_products_yahoo(start, query, num=batch_size)
            
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
            tqdm.write("キャッシュ済みの取引に到達したため、これ以降のページ取得を打ち切ります。")
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
        combined_df = cached_df
    
    # キャッシュ更新（.pkl形式で保存）
    combined_df.to_pickle(cache_file)
    
    # 最終的な最新終了日時を表示
    if not combined_df.empty:
        final_latest = combined_df['end_time'].max()
        print(f"[{query}] 最新の終了日時: {final_latest}")
    else:
        print(f"[{query}] データは取得されませんでした。")
    
    return combined_df

# ---------------------------
# 複数クエリ実行用関数
# ---------------------------
def query_word(queries, adult=False):
    """
    複数のクエリに対して取引データを取得し、重複を除いた上で終了日時順にソートして返す。
    
    Args:
        queries (list of str): 検索クエリのリスト
    
    Returns:
        pd.DataFrame: 全クエリの結合結果
    """
    dfs = []
    for query in queries:
        df = fetch_all_products_with_cache(query, total_items=15000, batch_size=50, cache_dir="cache_trade", adult=adult)
        dfs.append(df)
    final_df = pd.concat(dfs)
    final_df = final_df[~final_df.index.duplicated(keep='first')]
    final_df = final_df.sort_values("end_time")
    return final_df

# ---------------------------
# 実行例
# ---------------------------
if __name__ == '__main__':
    queries = [
        "アート ポスター",
        "アート イラスト",
        "ポスター",
        "A4",
        "AI",
    ]
    df = query_word(queries, adult=False)
    # print(f"総件数: {len(df)}")
    # print(df.head())