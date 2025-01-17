from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from io import StringIO
from lib.netprint import img2url_multi
from lxml import etree
from pathlib import Path
from PIL import Image
from PIL import Image
from requests_toolbelt.multipart.encoder import MultipartEncoder
from ruamel.yaml import YAML
from urllib.parse import urlparse, urlunparse, parse_qs, ParseResult
import functools
import glob
import hashlib
import json
import logging
import math
import matplotlib.pyplot as plt
import os
import pandas as pd
import re
import requests
import time
import urllib.parse
import itertools


SLEEP_TIME = 10



def initialize_logger(enable_stdout=True, log_file="auction.log"):
    """
    ロガーを初期化する関数

    Args:
        enable_stdout (bool): Trueの場合、標準出力にもログを表示
        log_file (str): ログファイルのパス
    """
    logger = logging.getLogger("listing_logger")
    logger.setLevel(logging.INFO)

    # 既存のハンドラをクリア
    if logger.hasHandlers():
        logger.handlers.clear()

    # フォーマットの設定
    log_format = "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, date_format)

    # ログファイルへの出力設定
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 標準出力への出力設定 (オプション)
    if enable_stdout:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


logger = initialize_logger(enable_stdout=False)  # 標準出力を無効




PREVIEW_TEMPLATE = {
    'aID': '',
    'oldAID': '',
    'mode': 'submit',
    'category': '2084047414',
    'md5': '8fa4896f6ce014f7a57e11fe788c4914f4f51af35f5ed54fc3253c9f8c070c601b166c92abf362dcf116050d0ae774ed5c9bc3220b2ee6a335ba838466a04749GwgI/TDzMVFbMmR+utfCN+tate2PJuqH5m2QViteWWOUbG3+bunPEOs/EvaoqidHZgOjL7ctpjA+bntRt8mudw==',
    '.crumb': '474ba23a33d3db7f9d486524940550ff488c2ba94bf6451efc4950eed3a666e0',
    'user_type': 'c',
    'dtl_img_crumb': 'aa3eca65c6743c8eb6c09eded5704d5199e79b2ac76f92c958041f876b81f866',
    'tos': 'yes',
    'isDraftChecked': '',
    'saveIndex': '0',
    'info01': '-540',
    'info02': '5',
    'info03': 'PDF Viewer|Chrome PDF Viewer|Chromium PDF Viewer|Microsoft Edge PDF Viewer|WebKit built-in PDF',
    'appraisal_info': '',
    'appraisal_select': '',
    'isY2S': '0',
    'y2sPattern': 'ineligible',
    'listing_type': '',
    'y2s_product_id': '',
    'y2s_department': '',
    'y2s_category_id': '',
    'y2s_sub_category_id': '',
    'y2s_brand_id': '',
    'y2s_tmpType': '',
    'y2s_tmpAucBrandId': '',
    'y2s_tmpSize': '',
    'submitTipsDisp': '0',
    'fnavi': '1',
    'fleamarket': '',
    'nonpremium': '1',
    'pagetype': 'form',
    'anchorPos': '',
    'Duration': '2',
    'ypmOK': '1',
    'Quantity': '1',
    'minBidRating': '0',
    'badRatingRatio': 'yes',
    'AutoExtension': '1',
    'CloseEarly': 'yes',
    'ClosingTime': '22',
    'draftIndex': '',
    'thumbNail': '/image/dr000/auc0512/user/38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9/i-thumb-173452964085499456745337.jpg:68',
    'image_comment1': '',
    'ImageFullPath1': 'https://auctions.c.yimg.jp/images.auctions.yahoo.co.jp/image/dr000/auc0512/user/38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9/i-img821x1200-17345296394750sofbet130690.jpg',
    'ImageWidth1': '821',
    'ImageHeight1': '1200',
    'image_comment2': '',
    'ImageFullPath2': 'https://auctions.c.yimg.jp/images.auctions.yahoo.co.jp/image/dr000/auc0512/user/38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9/i-img1200x1073-17345296349728thjbth159204.jpg',
    'ImageWidth2': '1200',
    'ImageHeight2': '1073',
    'image_comment3': '',
    'ImageFullPath3': '',
    'ImageWidth3': '',
    'ImageHeight3': '',
    'image_comment4': '',
    'ImageFullPath4': '',
    'ImageWidth4': '',
    'ImageHeight4': '',
    'image_comment5': '',
    'ImageFullPath5': '',
    'ImageWidth5': '',
    'ImageHeight5': '',
    'image_comment6': '',
    'ImageFullPath6': '',
    'ImageWidth6': '',
    'ImageHeight6': '',
    'image_comment7': '',
    'ImageFullPath7': '',
    'ImageWidth7': '',
    'ImageHeight7': '',
    'image_comment8': '',
    'ImageFullPath8': '',
    'ImageWidth8': '',
    'ImageHeight8': '',
    'image_comment9': '',
    'ImageFullPath9': '',
    'ImageWidth9': '',
    'ImageHeight9': '',
    'image_comment10': '',
    'ImageFullPath10': '',
    'ImageWidth10': '',
    'ImageHeight10': '',
    'auction_server': 'https://auctions.yahoo.co.jp/sell/jp',
    'uploadserver': 'sell.auctions.yahoo.co.jp',
    'ImageCntMax': '10',
    'ypoint': '0',
    'encode': 'utf-8',
    'Title': '【L判, 2L判, A4】アニメ コミック イラスト 筋肉 ゲイ ガチムチ セクシー 絵 3',
    'catalog_id': '',
    'catalog_jan_code': '',
    'catalog_name': '',
    'catalog_brand_id': '',
    'productSearchTitle': '',
    'submit_maker_brand_id': '',
    'brand_line_id': '',
    'item_segment_id': '',
    'item_spec_size_id': '',
    'item_spec_size_type': '',
    'istatus': 'new',
    'box_condition': '',
    'wrapping_paper_condition': '',
    'accessories': '',
    'retpolicy': '0',
    'submit_description': 'html',
    'Description': '',
    'Description_rte': '',
    'Description_rte_work': '',
    'Description_plain': '',
    'Description_plain_work': '',
    'shiptime': 'payment',
    'loc_cd': '27',
    'shipping': 'seller',
    'shippinginput': 'now',
    'shipping_dummy': 'seller',
    'itemsize': '',
    'itemweight': '',
    'is_yahuneko_nekoposu_ship': 'yes',
    'is_yahuneko_taqbin_compact_ship': '',
    'is_yahuneko_taqbin_ship': '',
    'is_jp_yupacket_official_ship': '',
    'is_jp_yupacket_post_mini_official_ship': '',
    'is_jp_yupacket_plus_official_ship': '',
    'is_jp_yupack_official_ship': '',
    'is_other_ship': '',
    'shipmethod_dummy': 'on',
    'shipschedule': '1',
    'ClosingYMD': '2024-12-20',
    'submitUnixtime': '1734529591',
    'tmpClosingYMD': '2024-12-20',
    'tmpClosingTime': '',
    'salesmode': 'auction',
    'StartPrice': '100',
    'BidOrBuyPrice': '990',
    'shipname1': '',
    'shipfee1': '',

}

# def parse_cookie_string(cookie_string):
#     """
#     Parse a cookie string into a dictionary.

#     Args:
#         cookie_string (str): Cookie string in standard format.

#     Returns:
#         dict: Parsed cookie as a dictionary.
#     """
#     cookie_dict = {}

#     # Remove "cookie: " prefix if present
#     if cookie_string.startswith("cookie: "):
#         cookie_string = cookie_string[len("cookie: "):]  # Strip the prefix

#     # Split by `;` to separate key-value pairs
#     items = cookie_string.split('; ')
    
#     for item in items:
#         # Split each item by the first `=` to get key and value
#         if '=' in item:
#             key, value = item.split('=', 1)
#             cookie_dict[key] = value

#     return cookie_dict



def post_img(file_path, headers, cookies, img_crumb, ):
    url = 'https://auctions.yahoo.co.jp/img/images/new'
    # multipart/form-data を動的に生成
    multipart_data = MultipartEncoder(
        fields={
            'files[0]': (file_path, open(file_path, 'rb'), 'image/jpeg'),
            '.crumb': img_crumb
        },
        boundary='----WebKitFormBoundary21zZxMEA7OXiANL6'
    )
    
    # # ヘッダー: boundaryは自動生成されるため動的に設定
    headers_pic = headers.copy()
    headers_pic['Content-Type'] = multipart_data.content_type

    # # # POSTリクエストを送信
    response = requests.post(url, headers=headers_pic, cookies=cookies, data=multipart_data)
    assert response.status_code == 200, f"画像アップロード失敗: {response.status_code}"
    assert response.json(), "Response がJSON形式ではありません"

    return response

# サムネイル取得
def get_thumbnail(path, headers, cookies, img_crumb, ):
    url = 'https://auctions.yahoo.co.jp/img/images/new'
    
    data = {
        '.crumb': img_crumb,
        'path': path,
    }
    headers_thumb = headers.copy()
    headers_thumb["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    
    thumb_response = requests.post(url, headers=headers_thumb, cookies=cookies, data=data)
    assert thumb_response.status_code == 200, f"画像アップロード失敗: {response.status_code}"
    assert thumb_response.json(), "Response がJSON形式ではありません"

    return thumb_response


def listing(cookies, file_path, title_name, description_rte, category = 2084047414, duration = 2, closing_hour = 21, start_price=100, end_price=990):

    # ヘッダー情報
    headers = {
        'accept': '*/*',
        'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
        'cache-control': 'no-cache',
        'origin': 'https://auctions.yahoo.co.jp',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://auctions.yahoo.co.jp/sell/jp/show/submit',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-arch': '"arm"',
        'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.71", "Chromium";v="131.0.6778.71", "Not_A Brand";v="24.0.0.0"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-platform-version': '"15.1.1"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
    }

    # オークション新規ページを開く
    url = f"https://auctions.yahoo.co.jp/sell/jp/show/submit?category={category}"
    response = requests.get(url, headers=headers, cookies=cookies)
    assert response.status_code == 200, f"リクエスト失敗: {response.status_code}"
    
    # レスポンスボディからHTMLを解析
    soup = BeautifulSoup(response.text, 'html.parser')
    img_crumb = soup.find('input', {'id': 'img_crumb'})['value']
    dtl_img_crumb = soup.find('input', {'name': 'dtl_img_crumb'})['value']
    _crumb = soup.find('input', {'name': '.crumb'})['value']
    md5 = soup.find('input', {'name': 'md5'})['value']
    assert img_crumb, "img_crumb の取得に失敗しました"
    assert dtl_img_crumb, "dtl_img_crumb の取得に失敗しました"
    assert _crumb, "_crumb の取得に失敗しました"
    assert md5, "md5 の取得に失敗しました"
    time.sleep(SLEEP_TIME)

    # 画像アップロード
    response=post_img(file_path, headers, cookies, img_crumb )
    thumb_response = get_thumbnail(response.json()["images"][0]["url"], headers, cookies, img_crumb)
    time.sleep(SLEEP_TIME)
    response_size=post_img('material/size.jpg', headers, cookies, img_crumb )
    time.sleep(SLEEP_TIME*3)

    # 出品プレビュー
    current_time = datetime.now()
    current_timestamp = int(time.mktime(current_time.timetuple()))
    end_time = current_time + timedelta(days=duration)    
    closing_ymd = end_time.strftime('%Y-%m-%d')
    data_update ={
        'category'       : category,
        'md5'            : md5,
        '.crumb'         : _crumb,
        'dtl_img_crumb'  : dtl_img_crumb,
        'thumbNail'      : thumb_response.json()["thumbnail"],
        'ImageFullPath1' : response.json()["images"][0]["url"],
        'ImageWidth1'    : response.json()["images"][0]["width"],
        'ImageHeight1'   : response.json()["images"][0]["height"],
        'ImageFullPath2' : response_size.json()["images"][0]["url"],
        'ImageWidth2'    : response_size.json()["images"][0]["width"],
        'ImageHeight2'   : response_size.json()["images"][0]["height"],
        'Title'          : title_name,
        'Description'    : description_rte,
        'Description_rte': description_rte, 
        'Duration'       : duration,
        'ClosingTime'    : closing_hour,
        'ClosingYMD'     : closing_ymd,
        'tmpClosingYMD'  : closing_ymd,
        'submitUnixtime' : str(current_timestamp),
        'StartPrice'     : start_price,
        'BidOrBuyPrice'  : end_price,
    }
    preview_data = PREVIEW_TEMPLATE.copy()
    preview_data.update(data_update)
    headers_prev = headers.copy()
    headers_prev["content-type"] = "application/x-www-form-urlencoded"
    url="https://auctions.yahoo.co.jp/sell/jp/show/preview"
    response_prev = requests.post(url, headers=headers_prev, cookies=cookies, data=preview_data)
    time.sleep(SLEEP_TIME)

    # 出品
    text="comefrprv=1&lastsubmit=1734462202&pagetype=preview&y2sPreviewSubmitStatus=0&mode=submit&category=2084047414&md5=ec600e010b11b28c919bf5a0ae9322b731569b9846085d608c6a2358b439a032fc31265d3bd2ccfc3eb169e85cdde87b9e1b6160c5c354e9c8b9d21d43d1e212odsFR4OO7U9ZgkC%2B5BqNgwP%2FII%2By0iRAPo9NPVoF5UNbYVm7%2FAulchCjJ%2BBbk2HvM13Ob5B05NlJbj6OCqJdbA%3D%3D&user_type=c&dtl_img_crumb=aa3eca65c6743c8eb6c09eded5704d5199e79b2ac76f92c958041f876b81f866&tos=yes&saveIndex=0&info01=-540&info02=5&info03=PDF+Viewer%7CChrome+PDF+Viewer%7CChromium+PDF+Viewer%7CMicrosoft+Edge+PDF+Viewer%7CWebKit+built-in+PDF&isY2S=0&y2sPattern=ineligible&submitTipsDisp=0&fnavi=1&nonpremium=1&pagetype=form&Duration=2&ypmOK=1&Quantity=1&minBidRating=0&badRatingRatio=yes&AutoExtension=yes&CloseEarly=yes&ClosingTime=0&thumbNail=%2Fimage%2Fdr000%2Fauc0512%2Fuser%2F38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9%2Fi-thumb-173453551394300992690286.jpg%3A68&ImageFullPath1=https%3A%2F%2Fauctions.c.yimg.jp%2Fimages.auctions.yahoo.co.jp%2Fimage%2Fdr000%2Fauc0512%2Fuser%2F38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9%2Fi-img821x1200-1734535513403947b4f0169877.jpg&ImageWidth1=821&ImageHeight1=1200&ImageFullPath2=https%3A%2F%2Fauctions.c.yimg.jp%2Fimages.auctions.yahoo.co.jp%2Fimage%2Fdr000%2Fauc0512%2Fuser%2F38edd9d6a9a5743638338e5e2fff5be9b4b9450557bab947c496249d536786a9%2Fi-img1200x1073-17345355160037tzwtss162067.jpg&ImageWidth2=1200&ImageHeight2=1073&auction_server=https%3A%2F%2Fauctions.yahoo.co.jp%2Fsell%2Fjp&uploadserver=sell.auctions.yahoo.co.jp&ImageCntMax=10&ypoint=0&encode=utf-8&Title=%E3%80%90L%E5%88%A4%2C+2L%E5%88%A4%2C+A4%E3%80%91%E3%82%A2%E3%83%8B%E3%83%A1+%E3%82%B3%E3%83%9F%E3%83%83%E3%82%AF+%E3%82%A4%E3%83%A9%E3%82%B9%E3%83%88+%E7%AD%8B%E8%82%89+%E3%82%B2%E3%82%A4+%E3%82%AC%E3%83%81%E3%83%A0%E3%83%81+%E3%82%BB%E3%82%AF%E3%82%B7%E3%83%BC+%E7%B5%B5+3&istatus=new&retpolicy=0&submit_description=html&Description=%3Cdiv+class%3D%22ProductExplanation%22+id%3D%22ProductExplanation%22+style%3D%22margin%3A+-70px+0px+40px%3B+padding%3A+70px+0px+0px%3B+font-family%3A+%26quot%3BHiragino+Kaku+Gothic+Pro%26quot%3B%2C+%26quot%3B%E3%83%92%E3%83%A9%E3%82%AE%E3%83%8E%E8%A7%92%E3%82%B4+Pro+W3%26quot%3B%2C+%E3%83%A1%E3%82%A4%E3%83%AA%E3%82%AA%2C+Meiryo%2C+%26quot%3B%EF%BC%AD%EF%BC%B3+%EF%BC%B0%E3%82%B4%E3%82%B7%E3%83%83%E3%82%AF%26quot%3B%2C+%26quot%3BMS+UI+Gothic%26quot%3B%2C+Helvetica%2C+Arial%2C+sans-serif%3B+font-size%3A+medium%3B%22%3E%3Cdiv+id%3D%22adoc%22+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B%22%3E%3Cdiv+class%3D%22ProductExplanation__body+highlightWordSearch%22+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+position%3A+relative%3B+width%3A+1320px%3B+overflow%3A+auto+hidden%3B%22%3E%3Cdiv+class%3D%22ProductExplanation__commentArea%22+style%3D%22margin%3A+0px+auto%3B+padding%3A+0px%3B%22%3E%3Cdiv+class%3D%22ProductExplanation__commentBody%22+style%3D%22margin%3A+0px%3B+padding%3A+0px+10px%3B+word-break%3A+break-all%3B+overflow-wrap%3A+break-word%3B+line-height%3A+1.4%3B%22%3E%3Ch3+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%22%3E%3Cspan+style%3D%22color%3A+%23333333%3B%22%3E%E2%97%8F%3C%2Fspan%3E%E3%81%8A%E5%B1%8A%E3%81%91%E6%96%B9%E6%B3%95%3C%2Fh3%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%26nbsp%3B%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E7%94%BB%E5%83%8F%E3%83%87%E3%83%BC%E3%82%BF%E3%81%AE%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89%3C%2Fspan%3E%26nbsp%3B%E3%81%8A%E3%82%88%E3%81%B3%26nbsp%3B%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%A7%E3%81%AE%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E7%94%A8%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%81%AE%E6%8F%90%E4%BE%9B%3C%2Fspan%3E%26nbsp%3B%E3%81%A7%E3%81%99%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E7%99%BA%E9%80%81%E3%81%AF%E8%A1%8C%E3%81%84%E3%81%BE%E3%81%9B%E3%82%93%E3%81%AE%E3%81%A7%E3%80%81%E3%81%82%E3%82%89%E3%81%8B%E3%81%98%E3%82%81%E3%81%94%E6%B3%A8%E6%84%8F%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3Cbr%3E%E8%B3%BC%E5%85%A5%E5%BE%8C%E3%81%AB%E7%99%BA%E8%A1%8C%E3%81%95%E3%82%8C%E3%81%9F%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%82%92%E5%88%A9%E7%94%A8%E3%81%97%E3%80%81%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%94%E8%87%AA%E8%BA%AB%E3%81%A7%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%AE%E3%83%9E%E3%83%AB%E3%83%81%E3%82%B3%E3%83%94%E3%83%BC%E6%A9%9F%E3%82%92%E4%BD%BF%E3%81%A3%E3%81%A6%E5%8D%B0%E5%88%B7%E3%81%84%E3%81%9F%E3%81%A0%E3%81%91%E3%81%BE%E3%81%99%E3%80%82%E4%BB%A5%E4%B8%8B%E3%81%AE%E3%82%B5%E3%82%A4%E3%82%BA%E3%82%84%E7%94%A8%E7%B4%99%E3%81%8B%E3%82%89%E9%81%B8%E6%8A%9E%E5%8F%AF%E8%83%BD%E3%81%A7%E3%81%99%EF%BC%9A%3C%2Fdiv%3E%3Cul+style%3D%22margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%22%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+L%E5%88%A4%3C%2Fspan%3E%26nbsp%3B%3A+30%E5%86%86%3C%2Fli%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+2L%E5%88%A4%3C%2Fspan%3E%26nbsp%3B%3A+80%E5%86%86%3C%2Fli%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%3Cspan+style%3D%22font-weight%3A+700%3B%22%3EA4+%28%E5%85%89%E6%B2%A2%E7%B4%99%29%3C%2Fspan%3E%26nbsp%3B%3A+120%E5%86%86%3C%2Fli%3E%3C%2Ful%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E2%80%BB%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E6%96%99%E9%87%91%E3%81%AF%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%AE%E3%81%94%E8%B2%A0%E6%8B%85%E3%81%A8%E3%81%AA%E3%82%8A%E3%81%BE%E3%81%99%E3%80%82%3Cbr%3E%E2%80%BB%E5%8D%B0%E5%88%B7%E5%86%85%E5%AE%B9%E3%81%AF%E6%9A%97%E5%8F%B7%E5%8C%96%E3%81%95%E3%82%8C%E3%81%A6%E3%81%8A%E3%82%8A%E3%80%81%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E5%BA%97%E5%93%A1%E3%82%84%E5%BA%97%E8%88%97%E3%81%8B%E3%82%89%E5%86%85%E5%AE%B9%E3%81%8C%E9%96%B2%E8%A6%A7%E3%81%95%E3%82%8C%E3%82%8B%E3%81%93%E3%81%A8%E3%81%AF%E3%81%82%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2Fdiv%3E%3Chr%3E%3Ch3+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%22%3E%3Cspan+style%3D%22color%3A+%23333333%3B%22%3E%E2%97%8F%3C%2Fspan%3E%E5%95%86%E5%93%81%E8%A9%B3%E7%B4%B0%3C%2Fh3%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%26nbsp%3B%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E9%AB%98%E7%B2%BE%E7%B4%B0%3C%2Fspan%3E%E3%81%AE%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%A2%E3%83%BC%E3%83%88%E3%83%9D%E3%82%B9%E3%82%BF%E3%83%BC%E3%81%A7%E3%81%99%E3%80%82%3Cbr%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E3%82%A6%E3%82%A9%E3%83%BC%E3%82%BF%E3%83%BC%E3%83%9E%E3%83%BC%E3%82%AF%E3%81%AF%E4%B8%80%E5%88%87%E5%85%A5%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E6%80%A7%E5%99%A8%E9%83%A8%E5%88%86%E3%81%AB%E9%81%A9%E5%88%87%E3%81%AA%E3%83%A2%E3%82%B6%E3%82%A4%E3%82%AF%E5%87%A6%E7%90%86%E3%81%8C%E6%96%BD%E3%81%95%E3%82%8C%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%22%3E%E5%87%BA%E5%93%81%E7%94%BB%E5%83%8F%E3%81%A7%E3%81%AF%E8%A6%8F%E7%B4%84%E3%81%AB%E5%9F%BA%E3%81%A5%E3%81%8D%E5%AE%8C%E5%85%A8%E3%81%AA%E4%BF%AE%E6%AD%A3%E3%82%92%E8%A1%8C%E3%81%A3%E3%81%9F%E4%B8%8A%E3%81%A7%E6%8E%B2%E8%BC%89%E3%81%97%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%81%AE%E3%81%A7%E3%80%81%E3%81%94%E4%BA%86%E6%89%BF%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3C%2Fdiv%3E%3Cul+style%3D%22margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%22%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%E3%81%94%E5%88%A9%E7%94%A8%E3%81%AE%E7%AB%AF%E6%9C%AB%E3%82%84%E3%83%A2%E3%83%8B%E3%82%BF%E3%83%BC%E3%81%AB%E3%82%88%E3%82%8A%E3%80%81%E5%AE%9F%E9%9A%9B%E3%81%AE%E5%8D%B0%E5%88%B7%E7%89%A9%E3%81%A8%E8%89%B2%E5%91%B3%E3%81%8C%E7%95%B0%E3%81%AA%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%E3%83%95%E3%83%81%E3%81%AA%E3%81%97%E5%8D%B0%E5%88%B7%E3%81%AE%E7%89%B9%E6%80%A7%E4%B8%8A%E3%80%81%E4%B8%8A%E4%B8%8B%E5%B7%A6%E5%8F%B3%E3%81%AB%E6%95%B0%E3%83%9F%E3%83%AA%E3%81%AE%E4%BD%99%E7%99%BD%E3%81%8C%E7%94%9F%E3%81%98%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3C%2Ful%3E%3Chr%3E%3Ch3+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%22%3E%3Cspan+style%3D%22color%3A+%23333333%3B%22%3E%E2%97%8F%3C%2Fspan%3E%E7%89%B9%E5%85%B8%E3%82%B5%E3%83%BC%E3%83%93%E3%82%B9%3C%2Fh3%3E%3Col+style%3D%22margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%22%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E%E5%8D%B3%E6%B1%BA%E4%BE%A1%E6%A0%BC%E3%81%A7%E3%81%AE%E8%90%BD%E6%9C%AD%E7%89%B9%E5%85%B8%3C%2Fspan%3E%3Cul+style%3D%22margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B%22%3E%3Cli+style%3D%22margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%22%3E%E5%90%8C%E3%81%98%E6%A7%8B%E5%9B%B3%E3%81%A7%E7%95%B0%E3%81%AA%E3%82%8B%E3%83%90%E3%83%AA%E3%82%A8%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E7%94%BB%E5%83%8F%E3%82%92%26nbsp%3B%3Cspan+style%3D%22font-weight%3A+700%3B%22%3E1%E7%A8%AE%E9%A1%9E%E8%BF%BD%E5%8A%A0%3C%2Fspan%3E%26nbsp%3B%E6%8F%90%E4%BE%9B%E3%81%84%E3%81%9F%E3%81%97%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3C%2Ful%3E%3C%2Fli%3E%3C%2Fol%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E&Description_rte=%3Cdiv+class%3D%2522ProductExplanation%2522+id%3D%2522ProductExplanation%2522+style%3D%2522margin%3A+-70px+0px+40px%3B+padding%3A+70px+0px+0px%3B+font-family%3A+%2526quot%3BHiragino+Kaku+Gothic+Pro%2526quot%3B%2C+%2526quot%3B%E3%83%92%E3%83%A9%E3%82%AE%E3%83%8E%E8%A7%92%E3%82%B4+Pro+W3%2526quot%3B%2C+%E3%83%A1%E3%82%A4%E3%83%AA%E3%82%AA%2C+Meiryo%2C+%2526quot%3B%EF%BC%AD%EF%BC%B3+%EF%BC%B0%E3%82%B4%E3%82%B7%E3%83%83%E3%82%AF%2526quot%3B%2C+%2526quot%3BMS+UI+Gothic%2526quot%3B%2C+Helvetica%2C+Arial%2C+sans-serif%3B+font-size%3A+medium%3B%2522%3E%3Cdiv+id%3D%2522adoc%2522+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B%2522%3E%3Cdiv+class%3D%2522ProductExplanation__body+highlightWordSearch%2522+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+position%3A+relative%3B+width%3A+1320px%3B+overflow%3A+auto+hidden%3B%2522%3E%3Cdiv+class%3D%2522ProductExplanation__commentArea%2522+style%3D%2522margin%3A+0px+auto%3B+padding%3A+0px%3B%2522%3E%3Cdiv+class%3D%2522ProductExplanation__commentBody%2522+style%3D%2522margin%3A+0px%3B+padding%3A+0px+10px%3B+word-break%3A+break-all%3B+overflow-wrap%3A+break-word%3B+line-height%3A+1.4%3B%2522%3E%3Ch3+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%2522%3E%3Cspan+style%3D%2522color%3A+%23333333%3B%2522%3E%E2%97%8F%3C%2Fspan%3E%E3%81%8A%E5%B1%8A%E3%81%91%E6%96%B9%E6%B3%95%3C%2Fh3%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%2526nbsp%3B%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E7%94%BB%E5%83%8F%E3%83%87%E3%83%BC%E3%82%BF%E3%81%AE%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89%3C%2Fspan%3E%2526nbsp%3B%E3%81%8A%E3%82%88%E3%81%B3%2526nbsp%3B%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%A7%E3%81%AE%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E7%94%A8%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%81%AE%E6%8F%90%E4%BE%9B%3C%2Fspan%3E%2526nbsp%3B%E3%81%A7%E3%81%99%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E7%99%BA%E9%80%81%E3%81%AF%E8%A1%8C%E3%81%84%E3%81%BE%E3%81%9B%E3%82%93%E3%81%AE%E3%81%A7%E3%80%81%E3%81%82%E3%82%89%E3%81%8B%E3%81%98%E3%82%81%E3%81%94%E6%B3%A8%E6%84%8F%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3Cbr%3E%E8%B3%BC%E5%85%A5%E5%BE%8C%E3%81%AB%E7%99%BA%E8%A1%8C%E3%81%95%E3%82%8C%E3%81%9F%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%82%92%E5%88%A9%E7%94%A8%E3%81%97%E3%80%81%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%94%E8%87%AA%E8%BA%AB%E3%81%A7%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%AE%E3%83%9E%E3%83%AB%E3%83%81%E3%82%B3%E3%83%94%E3%83%BC%E6%A9%9F%E3%82%92%E4%BD%BF%E3%81%A3%E3%81%A6%E5%8D%B0%E5%88%B7%E3%81%84%E3%81%9F%E3%81%A0%E3%81%91%E3%81%BE%E3%81%99%E3%80%82%E4%BB%A5%E4%B8%8B%E3%81%AE%E3%82%B5%E3%82%A4%E3%82%BA%E3%82%84%E7%94%A8%E7%B4%99%E3%81%8B%E3%82%89%E9%81%B8%E6%8A%9E%E5%8F%AF%E8%83%BD%E3%81%A7%E3%81%99%EF%BC%9A%3C%2Fdiv%3E%3Cul+style%3D%2522margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%2522%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+L%E5%88%A4%3C%2Fspan%3E%2526nbsp%3B%3A+30%E5%86%86%3C%2Fli%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+2L%E5%88%A4%3C%2Fspan%3E%2526nbsp%3B%3A+80%E5%86%86%3C%2Fli%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3EA4+%28%E5%85%89%E6%B2%A2%E7%B4%99%29%3C%2Fspan%3E%2526nbsp%3B%3A+120%E5%86%86%3C%2Fli%3E%3C%2Ful%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E2%80%BB%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E6%96%99%E9%87%91%E3%81%AF%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%AE%E3%81%94%E8%B2%A0%E6%8B%85%E3%81%A8%E3%81%AA%E3%82%8A%E3%81%BE%E3%81%99%E3%80%82%3Cbr%3E%E2%80%BB%E5%8D%B0%E5%88%B7%E5%86%85%E5%AE%B9%E3%81%AF%E6%9A%97%E5%8F%B7%E5%8C%96%E3%81%95%E3%82%8C%E3%81%A6%E3%81%8A%E3%82%8A%E3%80%81%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E5%BA%97%E5%93%A1%E3%82%84%E5%BA%97%E8%88%97%E3%81%8B%E3%82%89%E5%86%85%E5%AE%B9%E3%81%8C%E9%96%B2%E8%A6%A7%E3%81%95%E3%82%8C%E3%82%8B%E3%81%93%E3%81%A8%E3%81%AF%E3%81%82%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2Fdiv%3E%3Chr%3E%3Ch3+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%2522%3E%3Cspan+style%3D%2522color%3A+%23333333%3B%2522%3E%E2%97%8F%3C%2Fspan%3E%E5%95%86%E5%93%81%E8%A9%B3%E7%B4%B0%3C%2Fh3%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%2526nbsp%3B%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E9%AB%98%E7%B2%BE%E7%B4%B0%3C%2Fspan%3E%E3%81%AE%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%A2%E3%83%BC%E3%83%88%E3%83%9D%E3%82%B9%E3%82%BF%E3%83%BC%E3%81%A7%E3%81%99%E3%80%82%3Cbr%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E3%82%A6%E3%82%A9%E3%83%BC%E3%82%BF%E3%83%BC%E3%83%9E%E3%83%BC%E3%82%AF%E3%81%AF%E4%B8%80%E5%88%87%E5%85%A5%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E6%80%A7%E5%99%A8%E9%83%A8%E5%88%86%E3%81%AB%E9%81%A9%E5%88%87%E3%81%AA%E3%83%A2%E3%82%B6%E3%82%A4%E3%82%AF%E5%87%A6%E7%90%86%E3%81%8C%E6%96%BD%E3%81%95%E3%82%8C%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fdiv%3E%3Cdiv+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+color%3A+%23000000%3B%2522%3E%E5%87%BA%E5%93%81%E7%94%BB%E5%83%8F%E3%81%A7%E3%81%AF%E8%A6%8F%E7%B4%84%E3%81%AB%E5%9F%BA%E3%81%A5%E3%81%8D%E5%AE%8C%E5%85%A8%E3%81%AA%E4%BF%AE%E6%AD%A3%E3%82%92%E8%A1%8C%E3%81%A3%E3%81%9F%E4%B8%8A%E3%81%A7%E6%8E%B2%E8%BC%89%E3%81%97%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%81%AE%E3%81%A7%E3%80%81%E3%81%94%E4%BA%86%E6%89%BF%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3C%2Fdiv%3E%3Cul+style%3D%2522margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%2522%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%E3%81%94%E5%88%A9%E7%94%A8%E3%81%AE%E7%AB%AF%E6%9C%AB%E3%82%84%E3%83%A2%E3%83%8B%E3%82%BF%E3%83%BC%E3%81%AB%E3%82%88%E3%82%8A%E3%80%81%E5%AE%9F%E9%9A%9B%E3%81%AE%E5%8D%B0%E5%88%B7%E7%89%A9%E3%81%A8%E8%89%B2%E5%91%B3%E3%81%8C%E7%95%B0%E3%81%AA%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%E3%83%95%E3%83%81%E3%81%AA%E3%81%97%E5%8D%B0%E5%88%B7%E3%81%AE%E7%89%B9%E6%80%A7%E4%B8%8A%E3%80%81%E4%B8%8A%E4%B8%8B%E5%B7%A6%E5%8F%B3%E3%81%AB%E6%95%B0%E3%83%9F%E3%83%AA%E3%81%AE%E4%BD%99%E7%99%BD%E3%81%8C%E7%94%9F%E3%81%98%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3C%2Ful%3E%3Chr%3E%3Ch3+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+font-size%3A+16px%3B+font-weight%3A+400%3B+color%3A+%23000000%3B%2522%3E%3Cspan+style%3D%2522color%3A+%23333333%3B%2522%3E%E2%97%8F%3C%2Fspan%3E%E7%89%B9%E5%85%B8%E3%82%B5%E3%83%BC%E3%83%93%E3%82%B9%3C%2Fh3%3E%3Col+style%3D%2522margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B+color%3A+%23000000%3B%2522%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E%E5%8D%B3%E6%B1%BA%E4%BE%A1%E6%A0%BC%E3%81%A7%E3%81%AE%E8%90%BD%E6%9C%AD%E7%89%B9%E5%85%B8%3C%2Fspan%3E%3Cul+style%3D%2522margin%3A+0px%3B+padding%3A+0px+0px+0px+25px%3B%2522%3E%3Cli+style%3D%2522margin%3A+0px%3B+padding%3A+0px%3B+list-style%3A+inherit%3B%2522%3E%E5%90%8C%E3%81%98%E6%A7%8B%E5%9B%B3%E3%81%A7%E7%95%B0%E3%81%AA%E3%82%8B%E3%83%90%E3%83%AA%E3%82%A8%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E7%94%BB%E5%83%8F%E3%82%92%2526nbsp%3B%3Cspan+style%3D%2522font-weight%3A+700%3B%2522%3E1%E7%A8%AE%E9%A1%9E%E8%BF%BD%E5%8A%A0%3C%2Fspan%3E%2526nbsp%3B%E6%8F%90%E4%BE%9B%E3%81%84%E3%81%9F%E3%81%97%E3%81%BE%E3%81%99%E3%80%82%3C%2Fli%3E%3C%2Ful%3E%3C%2Fli%3E%3C%2Fol%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E%3C%2Fdiv%3E&shiptime=payment&loc_cd=27&shipping=seller&shippinginput=now&shipping_dummy=seller&is_yahuneko_nekoposu_ship=yes&is_yahuneko_taqbin_compact_ship=&is_yahuneko_taqbin_ship=&is_jp_yupacket_official_ship=&is_jp_yupack_official_ship=&shipmethod_dummy=on&shipschedule=1&ClosingYMD=2024-12-21&submitUnixtime=1734535447&tmpClosingYMD=2024-12-21&salesmode=auction&StartPrice=100&BidOrBuyPrice=990&browserAcceptLanguage=ja&ipCountryCode=jp&shipname1=&shipfee1=&hokkaidoshipping1=&okinawashipping1=&isolatedislandshipping1=&longdistshipping1=&shipname2=&shipfee2=&hokkaidoshipping2=&okinawashipping2=&isolatedislandshipping2=&longdistshipping2=&shipname3=&shipfee3=&hokkaidoshipping3=&okinawashipping3=&isolatedislandshipping3=&longdistshipping3=&shipname4=&shipfee4=&hokkaidoshipping4=&okinawashipping4=&isolatedislandshipping4=&longdistshipping4=&shipname5=&shipfee5=&hokkaidoshipping5=&okinawashipping5=&isolatedislandshipping5=&longdistshipping5=&shipname6=&shipfee6=&hokkaidoshipping6=&okinawashipping6=&isolatedislandshipping6=&longdistshipping6=&shipname7=&shipfee7=&hokkaidoshipping7=&okinawashipping7=&isolatedislandshipping7=&longdistshipping7=&shipname8=&shipfee8=&hokkaidoshipping8=&okinawashipping8=&isolatedislandshipping8=&longdistshipping8=&shipname9=&shipfee9=&hokkaidoshipping9=&okinawashipping9=&isolatedislandshipping9=&longdistshipping9=&shipname10=&shipfee10=&hokkaidoshipping10=&okinawashipping10=&isolatedislandshipping10=&longdistshipping10=&categoryPath=%E3%82%AA%E3%83%BC%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E3%83%88%E3%83%83%E3%83%97+%3E+%E3%81%9D%E3%81%AE%E4%BB%96+%3E+%E3%82%A2%E3%83%80%E3%83%AB%E3%83%88+%3E+%E3%82%B2%E3%82%A4%E5%90%91%E3%81%91+%3E+%E3%81%9D%E3%81%AE%E4%BB%96&LastStartPrice=&startDate=1734535447&endDate=1734708247&location=%E5%A4%A7%E9%98%AA%E5%BA%9C&JpYPayAllowed=true&allowPayPay=false&aspj3=&aspj4=&istatus_comment=&retpolicy_comment=&charityOption=&bidCreditLimit=0&Offer=0&numResubmit=0&initNumResubmit=&markdown_ratio=&markdownPrice1=&markdownPrice2=&markdownPrice3=&ReservePrice=&featuredAmount=&GiftIconName=&itemsizeStr=%EF%BC%8D&itemweightStr=%EF%BC%8D&ypkOK=&hacoboon_shipratelink=&intlOK=0&affiliate=0&affiliateRate=&mgc=A6PpYmcAAHN8YR22NglhzMtDl90RE4ycGkAfnSERICXAz5MTq6UwA1ZS4JLutLzgeBblD%2FMvMMGdoHEgCfKd%2FJWCT%2Fyy9Gg86jcEK30AnWM0pOD82CYF37Wm%2Bh3Hp%2BR9bCDeZedRdTU3z50a2CNgeFwz0qF%2ByjbxUyCOrMKSCPbIkYodVo75t7IJvEznwi%2F8NP88EVfm1iO%2BYkoGSkXuozFHBdvkwNgJt0xKksGdaDJzt5Hhl9IiwUAfyzKuqw%3D%3D&cpaAmount=&initialFeaturedCharge=&DurationDetail=&BoldFaceCharge=&HighlightListingCharge=&GiftIconCharge=&WrappingIconCharge=&ReserveFeeOnly=&reserveFeeTotal=&SpecificFeeOnly=0&insertionFeeTotal=0&fixedOrderFeePerOne=0&totalCharges=0&IsPrivacyDeliveryAvailable=&ManualStartTime=1970-01-01T09%3A00%3A00%2B09%3A00&brand_line_id=&brand_line_name=&item_spec_size_id=&item_spec_size_type=&item_spec_size=&item_segment_id=&item_segment=&catalog_id=&catalog_jan_code=&catalog_name=&appraisal_code=&markdown=0&Description_disp=+%3CDIV+STYLE%3D%22+%22%3E%3CDIV+STYLE%3D%22+%22%3E%3CDIV+STYLE%3D%22+%22%3E%3CDIV+STYLE%3D%22+%22%3E%3CDIV+STYLE%3D%22+%22%3E%3CH3+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CSPAN+STYLE%3D%22COLOR%3A+%23333333%3B%22%3E%E2%97%8F%3C%2FSPAN%3E%E3%81%8A%E5%B1%8A%E3%81%91%E6%96%B9%E6%B3%95%3C%2FH3%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%26nbsp%3B%3CSPAN+STYLE%3D%22+%22%3E%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E7%94%BB%E5%83%8F%E3%83%87%E3%83%BC%E3%82%BF%E3%81%AE%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89%3C%2FSPAN%3E%26nbsp%3B%E3%81%8A%E3%82%88%E3%81%B3%26nbsp%3B%3CSPAN+STYLE%3D%22+%22%3E%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%A7%E3%81%AE%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E7%94%A8%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%81%AE%E6%8F%90%E4%BE%9B%3C%2FSPAN%3E%26nbsp%3B%E3%81%A7%E3%81%99%E3%80%82%3C%2FDIV%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E7%99%BA%E9%80%81%E3%81%AF%E8%A1%8C%E3%81%84%E3%81%BE%E3%81%9B%E3%82%93%E3%81%AE%E3%81%A7%E3%80%81%E3%81%82%E3%82%89%E3%81%8B%E3%81%98%E3%82%81%E3%81%94%E6%B3%A8%E6%84%8F%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3CBR%3E%E8%B3%BC%E5%85%A5%E5%BE%8C%E3%81%AB%E7%99%BA%E8%A1%8C%E3%81%95%E3%82%8C%E3%81%9F%E3%82%B7%E3%83%AA%E3%82%A2%E3%83%AB%E3%82%B3%E3%83%BC%E3%83%89%E3%82%92%E5%88%A9%E7%94%A8%E3%81%97%E3%80%81%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%94%E8%87%AA%E8%BA%AB%E3%81%A7%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E3%81%AE%E3%83%9E%E3%83%AB%E3%83%81%E3%82%B3%E3%83%94%E3%83%BC%E6%A9%9F%E3%82%92%E4%BD%BF%E3%81%A3%E3%81%A6%E5%8D%B0%E5%88%B7%E3%81%84%E3%81%9F%E3%81%A0%E3%81%91%E3%81%BE%E3%81%99%E3%80%82%E4%BB%A5%E4%B8%8B%E3%81%AE%E3%82%B5%E3%82%A4%E3%82%BA%E3%82%84%E7%94%A8%E7%B4%99%E3%81%8B%E3%82%89%E9%81%B8%E6%8A%9E%E5%8F%AF%E8%83%BD%E3%81%A7%E3%81%99%EF%BC%9A%3C%2FDIV%3E%3CUL+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CLI+STYLE%3D%22+%22%3E%3CSPAN+STYLE%3D%22+%22%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+L%E5%88%A4%3C%2FSPAN%3E%26nbsp%3B%3A+30%E5%86%86%3CLI+STYLE%3D%22+%22%3E%3CSPAN+STYLE%3D%22+%22%3E%E5%86%99%E7%9C%9F%E7%94%A8%E7%B4%99+2L%E5%88%A4%3C%2FSPAN%3E%26nbsp%3B%3A+80%E5%86%86%3CLI+STYLE%3D%22+%22%3E%3CSPAN+STYLE%3D%22+%22%3EA4+%28%E5%85%89%E6%B2%A2%E7%B4%99%29%3C%2FSPAN%3E%26nbsp%3B%3A+120%E5%86%86%3C%2FUL%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E2%80%BB%E3%83%97%E3%83%AA%E3%83%B3%E3%83%88%E6%96%99%E9%87%91%E3%81%AF%E8%90%BD%E6%9C%AD%E8%80%85%E6%A7%98%E3%81%AE%E3%81%94%E8%B2%A0%E6%8B%85%E3%81%A8%E3%81%AA%E3%82%8A%E3%81%BE%E3%81%99%E3%80%82%3CBR%3E%E2%80%BB%E5%8D%B0%E5%88%B7%E5%86%85%E5%AE%B9%E3%81%AF%E6%9A%97%E5%8F%B7%E5%8C%96%E3%81%95%E3%82%8C%E3%81%A6%E3%81%8A%E3%82%8A%E3%80%81%E3%82%B3%E3%83%B3%E3%83%93%E3%83%8B%E5%BA%97%E5%93%A1%E3%82%84%E5%BA%97%E8%88%97%E3%81%8B%E3%82%89%E5%86%85%E5%AE%B9%E3%81%8C%E9%96%B2%E8%A6%A7%E3%81%95%E3%82%8C%E3%82%8B%E3%81%93%E3%81%A8%E3%81%AF%E3%81%82%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2FDIV%3E%3CHR%3E%3CH3+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CSPAN+STYLE%3D%22COLOR%3A+%23333333%3B%22%3E%E2%97%8F%3C%2FSPAN%3E%E5%95%86%E5%93%81%E8%A9%B3%E7%B4%B0%3C%2FH3%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E6%9C%AC%E5%95%86%E5%93%81%E3%81%AF%26nbsp%3B%3CSPAN+STYLE%3D%22+%22%3E%E9%AB%98%E7%B2%BE%E7%B4%B0%3C%2FSPAN%3E%E3%81%AE%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%A2%E3%83%BC%E3%83%88%E3%83%9D%E3%82%B9%E3%82%BF%E3%83%BC%E3%81%A7%E3%81%99%E3%80%82%3CBR%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E3%82%A6%E3%82%A9%E3%83%BC%E3%82%BF%E3%83%BC%E3%83%9E%E3%83%BC%E3%82%AF%E3%81%AF%E4%B8%80%E5%88%87%E5%85%A5%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%E3%80%82%3C%2FDIV%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E5%95%86%E5%93%81%E3%81%AB%E3%81%AF%E6%80%A7%E5%99%A8%E9%83%A8%E5%88%86%E3%81%AB%E9%81%A9%E5%88%87%E3%81%AA%E3%83%A2%E3%82%B6%E3%82%A4%E3%82%AF%E5%87%A6%E7%90%86%E3%81%8C%E6%96%BD%E3%81%95%E3%82%8C%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2FDIV%3E%3CDIV+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%E5%87%BA%E5%93%81%E7%94%BB%E5%83%8F%E3%81%A7%E3%81%AF%E8%A6%8F%E7%B4%84%E3%81%AB%E5%9F%BA%E3%81%A5%E3%81%8D%E5%AE%8C%E5%85%A8%E3%81%AA%E4%BF%AE%E6%AD%A3%E3%82%92%E8%A1%8C%E3%81%A3%E3%81%9F%E4%B8%8A%E3%81%A7%E6%8E%B2%E8%BC%89%E3%81%97%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%81%AE%E3%81%A7%E3%80%81%E3%81%94%E4%BA%86%E6%89%BF%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%3C%2FDIV%3E%3CUL+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CLI+STYLE%3D%22+%22%3E%E3%81%94%E5%88%A9%E7%94%A8%E3%81%AE%E7%AB%AF%E6%9C%AB%E3%82%84%E3%83%A2%E3%83%8B%E3%82%BF%E3%83%BC%E3%81%AB%E3%82%88%E3%82%8A%E3%80%81%E5%AE%9F%E9%9A%9B%E3%81%AE%E5%8D%B0%E5%88%B7%E7%89%A9%E3%81%A8%E8%89%B2%E5%91%B3%E3%81%8C%E7%95%B0%E3%81%AA%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3CLI+STYLE%3D%22+%22%3E%E3%83%95%E3%83%81%E3%81%AA%E3%81%97%E5%8D%B0%E5%88%B7%E3%81%AE%E7%89%B9%E6%80%A7%E4%B8%8A%E3%80%81%E4%B8%8A%E4%B8%8B%E5%B7%A6%E5%8F%B3%E3%81%AB%E6%95%B0%E3%83%9F%E3%83%AA%E3%81%AE%E4%BD%99%E7%99%BD%E3%81%8C%E7%94%9F%E3%81%98%E3%82%8B%E5%A0%B4%E5%90%88%E3%81%8C%E3%81%94%E3%81%96%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%3C%2FUL%3E%3CHR%3E%3CH3+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CSPAN+STYLE%3D%22COLOR%3A+%23333333%3B%22%3E%E2%97%8F%3C%2FSPAN%3E%E7%89%B9%E5%85%B8%E3%82%B5%E3%83%BC%E3%83%93%E3%82%B9%3C%2FH3%3E%3COL+STYLE%3D%22+COLOR%3A+%23000000%3B%22%3E%3CLI+STYLE%3D%22+%22%3E%3CSPAN+STYLE%3D%22+%22%3E%E5%8D%B3%E6%B1%BA%E4%BE%A1%E6%A0%BC%E3%81%A7%E3%81%AE%E8%90%BD%E6%9C%AD%E7%89%B9%E5%85%B8%3C%2FSPAN%3E%3CUL+STYLE%3D%22+%22%3E%3CLI+STYLE%3D%22+%22%3E%E5%90%8C%E3%81%98%E6%A7%8B%E5%9B%B3%E3%81%A7%E7%95%B0%E3%81%AA%E3%82%8B%E3%83%90%E3%83%AA%E3%82%A8%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E7%94%BB%E5%83%8F%E3%82%92%26nbsp%3B%3CSPAN+STYLE%3D%22+%22%3E1%E7%A8%AE%E9%A1%9E%E8%BF%BD%E5%8A%A0%3C%2FSPAN%3E%26nbsp%3B%E6%8F%90%E4%BE%9B%E3%81%84%E3%81%9F%E3%81%97%E3%81%BE%E3%81%99%E3%80%82%3C%2FUL%3E%3C%2FOL%3E%3C%2FDIV%3E%3C%2FDIV%3E%3C%2FDIV%3E%3C%2FDIV%3E%3C%2FDIV%3E+&paymethod1=&paymethod2=&paymethod3=&paymethod4=&paymethod5=&paymethod6=&paymethod7=&paymethod8=&paymethod9=&paymethod10=&shipnameWithSuffix1=&shipratelink1=&shipnameWithSuffix2=&shipratelink2=&shipnameWithSuffix3=&shipratelink3=&shipnameWithSuffix4=&shipratelink4=&shipnameWithSuffix5=&shipratelink5=&shipnameWithSuffix6=&shipratelink6=&shipnameWithSuffix7=&shipratelink7=&shipnameWithSuffix8=&shipratelink8=&shipnameWithSuffix9=&shipratelink9=&shipnameWithSuffix10=&shipratelink10=&image_comment1=&image_comment2=&ImageFullPath3=&image_comment3=&ImageFullPath4=&image_comment4=&ImageFullPath5=&image_comment5=&ImageFullPath6=&image_comment6=&ImageFullPath7=&image_comment7=&ImageFullPath8=&image_comment8=&ImageFullPath9=&image_comment9=&ImageFullPath10=&image_comment10=&bkname1=&bkname2=&bkname3=&bkname4=&bkname5=&bkname6=&bkname7=&bkname8=&bkname9=&bkname10=&hacoboonMiniFeeInfoAreaName1=&hacoboonMiniFeeInfoFee1=&hacoboonMiniFeeInfoAreaName2=&hacoboonMiniFeeInfoFee2=&hacoboonMiniFeeInfoAreaName3=&hacoboonMiniFeeInfoFee3=&hacoboonMiniFeeInfoAreaName4=&hacoboonMiniFeeInfoFee4=&hacoboonMiniCvsPref=&aspj1=&isYahunekoPack=true&isFirstSubmit=&is_hb_ship=&hb_shipratelink=&hb_ship_fee=&hb_hokkaido_ship_fee=&hb_okinawa_ship_fee=&hb_isolatedisland_ship_fee=&hb_deliveryfeesize=&is_hbmini_ship=&yahuneko_taqbin_deliveryfeesize=&is_jp_yupacket_post_mini_official_ship=&is_jp_yupacket_plus_official_ship=&jp_yupack_deliveryfeesize=&.crumb=474ba23a33d3db7f9d486524940550ff488c2ba94bf6451efc4950eed3a666e0&comefrprv=1&draftIndex=&is_paypay_fleamarket_cross_listing=0"
    decoded_data = dict(urllib.parse.parse_qsl(text, keep_blank_values=True))
    soup = BeautifulSoup(response_prev.text, 'html.parser')
    error_box = soup.select_one('#wrapper > div.decErrorBox')
    if error_box is not None:
        error_msg = error_box.get_text(strip=True, separator="\n")
        print(error_msg)
        logger.info("出品済みのためスキップしました"+error_msg)
        return True, response_prev
        
    data_submit = {}
    for k,v in decoded_data.items():
        if k in ["draftIndex"]: continue
        dom = soup.find('input', {'name': k})
        if dom is None:
            raise ValueError(
                f"Error: Key '{k}' not found in the HTML input elements.\n"
                f"Soup content:\n{soup.prettify()}"
            )
        data_submit[k] = dom['value']
    data_submit["draftIndex"] = ""
    headers_submit = headers.copy()
    headers_submit["referer"] = "https://auctions.yahoo.co.jp/sell/jp/show/preview"
    headers_submit["content-type"] = "application/x-www-form-urlencoded"
    url="https://auctions.yahoo.co.jp/sell/jp/config/submit"
    response_submit = requests.post(url, headers=headers_submit, cookies=cookies, data=data_submit)
    assert response_submit.status_code == 200, f"リクエスト失敗: {response.status_code}"
    
    # 出品結果の確認
    soup = BeautifulSoup(response_submit.text, "html.parser")
    dom = soup.find('a', string='このオークションの商品ページを見る')
    if dom is not None:
        auction_url = dom['href']
        logger.info(f"出品成功: {auction_url}")
        # os.remove(file_path)
        result = True
    else:
        error_message = soup.select_one("#modAlertBox .decJS")
        result = False
        logger.error(error_message)

    return result, response_submit



# Enumの定義
class TransactionStatus(Enum):
    INITIATED = 1  # 取引情報
    PAYMENT = 2           # お支払い
    SHIPPING = 3          # 発送連絡
    RECEIPT = 4         # 受取連絡

# クラス名をパースしてステータスを取得する関数
def parse_status_from_class(class_name):
    # クラス名からステータス番号を抽出 (例: "--current03" -> 3)
    match = re.search(r"--current(\d+)", class_name)
    if not match:
        return None
    status_number = int(match.group(1))

    # Enumから対応するステータスを取得
    for status in TransactionStatus:
        if status.value == status_number:
            return status
    return None



def load_config(file_path):
    yaml = YAML()
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.load(f), yaml

def save_config(file_path, config, yaml):
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)


def parse_cookie_string(cookies_list):
    """
    Parse a cookie string into a dictionary.

    Args:
        cookie_string (str): Cookie string in standard format.

    Returns:
        dict: Parsed cookie as a dictionary.
    """
    session = requests.Session()
    for cookie in cookies_list:
        session.cookies.set(
            cookie['name'],
            cookie['value'],
            domain=cookie['domain'],
            path=cookie['path']
        )
    return session.cookies


def serialize_cookies(cookies):
    return  [
        {
            "domain": cookie.domain,
            "expirationDate": float(cookie.expires) if cookie.expires else None,
            "hostOnly": not cookie.domain_initial_dot,
            "httpOnly": "HttpOnly" in cookie._rest,
            "name": cookie.name,
            "path": cookie.path,
            "sameSite": "unspecified",
            "secure": cookie.secure,
            "session": cookie.discard,
            "storeId": "0",
            "value": cookie.value,
        }
        for cookie in cookies
    ]


FILE_REGEX=r".+/[a-z]+_[0-9a-f]{6}\.jpg$"

def get_original_files(pattern="data/items/*/*.jpg"):
    """元画像のみを取得し、更新日時が早い順にソート"""
    files = glob.glob(pattern)
    original_files = [file for file in files if re.match(FILE_REGEX, file)]
    # 更新日時でソート
    return sorted(original_files, key=os.path.getmtime, reverse=True)

def get_original_files_with_tags(tags, base_pattern="data/items/{}/*.jpg", suffix="sample"):
    """
    元画像のみを取得し、更新日時が早い順にソート
    :param tags: マッチさせたいタグのリスト (例: ["a", "b"])
    :param base_pattern: ベースとなるパターン (デフォルトは "data/items/{}/**/*.jpg")
    """
    if suffix != "":
        suffix = f"_{suffix}"

    assert isinstance(tags, list), tags
    files = []
    for tag in tags:
        # 各タグごとにパターンを生成してマッチするファイルを取得
        pattern = base_pattern.format(tag)
        files.extend(glob.glob(pattern, recursive=True))  # recursive=Trueで再帰的に検索
    
    # フィルタリング
    original_files = [file for file in files if re.match(FILE_REGEX, file)]
    # print(original_files)
    # 更新日時でソートして返す
    files = sorted(original_files, key=os.path.getmtime, reverse=True)  # reverse=Trueで新しい順にソート
    file_paths = [f"{file_path.rsplit('.', 1)[0]}{suffix}.jpg" for file_path in files]
    assert all([os.path.exists(f) for f in files]), files
    assert all([os.path.exists(f) for f in file_paths]), file_paths
    return file_paths


def get_hash(file_path):
    pattern = r"[a-z]+_[0-9a-f]{6}"
    
    # 正規表現でマッチ
    match = re.search(pattern, file_path)
    if match:
        extracted = match.group()
        return extracted

def get_purchased():
    # JSONファイルが保存されているディレクトリ
    directory = "./print_qr/"
    
    # ユニークなファイルリストを保持するセット
    unique_files = set()
    
    # ディレクトリ内のすべてのJSONファイルを処理
    for file_name in os.listdir(directory):
        if file_name.endswith(".json"):  # JSONファイルのみを対象
            file_path = os.path.join(directory, file_name)
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    if "files" in data:
                        unique_files.update(data["files"])  # filesをセットに追加
            except (json.JSONDecodeError, KeyError):
                pass
                # print(f"JSONエラーまたはキーエラー: {file_path}")
    
    unique_files = [get_hash(i) for i in unique_files if get_hash(i)]
    # ユニークなファイルリストをソートして出力
    unique_files = sorted(unique_files)
    return set(unique_files)

def get_listed(processed_file="processed_hashes.txt"):
    hash_file_path = Path(processed_file)
    return set(hash_file_path.read_text(encoding="utf-8").splitlines()) if hash_file_path.exists() else set()    

def get_file_exclude(file_paths, processed_hashes=None):
    if processed_hashes is None:
        processed_hashes = (get_purchased() | get_listed())
    return [file_path for file_path in file_paths if get_hash(file_path) not in processed_hashes]


def convert_to_div_based_html(description):
    """
    Markdown形式のリンク、太字、リスト、見出しをHTML形式に変換しつつ、divベースのHTMLを生成する
    """
    # 正規表現パターン
    markdown_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    bold_text_pattern = r'\*\*(.*?)\*\*'
    list_item_pattern = r'^\s*\*\s+(.*)'
    heading_pattern = r'^(#{1,6})\s*(.*)'

    def replace_markdown_syntax(line):
        """
        Markdownリンク、太字、リスト、見出しをHTMLに変換
        """
        # 見出しの変換
        if re.match(heading_pattern, line):
            match = re.match(heading_pattern, line)
            level = len(match.group(1))
            text = match.group(2)
            font_size = max(7 - level, 1)  # 見出しのレベルに応じてフォントサイズを調整
            return f'<div><font size="{font_size}">{text}</font></div>'

        # リストアイテムの変換
        if re.match(list_item_pattern, line):
            return re.sub(list_item_pattern, r'<li>\1</li>', line)

        # その他の変換
        line = re.sub(markdown_link_pattern, r'<a href="\2" target="_blank">\1</a>', line)
        line = re.sub(bold_text_pattern, r'<b>\1</b>', line)
        return line

    html_lines = []
    in_list = False

    for line in description.splitlines():
        stripped_line = line.strip()

        if re.match(list_item_pattern, stripped_line):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(replace_markdown_syntax(stripped_line))
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<div>{replace_markdown_syntax(stripped_line)}</div>' if stripped_line else '<div><br></div>'
            )

    if in_list:  # リストが閉じられずに終わった場合
        html_lines.append('</ul>')

    return "".join(html_lines)

def remove(id_to_remove):
    # ファイルから現在のハッシュセットを読み込む
    processed_hashes = set(hash_file_path.read_text(encoding="utf-8").splitlines()) if hash_file_path.exists() else set()
    
    # 指定されたIDがセットに含まれるかを確認
    assert id_to_remove in processed_hashes, f"{id_to_remove} is not in processed_hashes"
    
    # IDをセットから削除
    processed_hashes.remove(id_to_remove)
    
    # ファイルに更新後のハッシュセットを書き込む
    hash_file_path.write_text("\n".join(processed_hashes), encoding="utf-8")
    
    print(f"{id_to_remove} was successfully removed.")

# 使用例
# remove("a_fbcecf")


productname_to_imgid = lambda x: re.search(r'[a-zA-Z]_[a-zA-Z0-9]{6}', x).group() if re.search(r'[a-zA-Z]_[a-zA-Z0-9]{6}', x) else None

# def get_table(cookies, url, index_col=0, table_class='ItemTable', referer='https://auctions.yahoo.co.jp/user/jp/show/mystatus',):

#     # ヘッダー情報
#     headers = {
#         'accept': '*/*',
#         'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
#         'cache-control': 'no-cache',
#         'origin': 'https://auctions.yahoo.co.jp',
#         'pragma': 'no-cache',
#         'priority': 'u=1, i',
#         'referer': referer, 
#         'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
#         'sec-ch-ua-arch': '"arm"',
#         'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.71", "Chromium";v="131.0.6778.71", "Not_A Brand";v="24.0.0.0"',
#         'sec-ch-ua-mobile': '?0',
#         'sec-ch-ua-model': '""',
#         'sec-ch-ua-platform': '"macOS"',
#         'sec-ch-ua-platform-version': '"15.1.1"',
#         'sec-fetch-dest': 'empty',
#         'sec-fetch-mode': 'cors',
#         'sec-fetch-site': 'same-origin',
#         'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
#         'x-requested-with': 'XMLHttpRequest'
#     }

#     # オークション新規ページを開く
#     page=1
#     response = requests.get(url, headers=headers, cookies=cookies)
#     assert response.status_code == 200, f"リクエスト失敗: {response.status_code}"
    
#     soup = BeautifulSoup(response.text, 'html.parser')

#     try:
#         tables = pd.read_html(StringIO(response.text), attrs={'class': table_class}, flavor='bs4',extract_links="body",index_col=index_col, header=0)
#     except:
#         return response
#     df_tmp = tables[0].dropna(how="all")
#     df_tmp = df_tmp.reset_index()
    
#     # DataFrameを辞書形式に変換
#     data = df_tmp.to_dict(orient="records")
    
#     df_tmp = pd.DataFrame([{key[0]: value for key, value in record.items()} for record in data])
#     current_year = datetime.now().year
    
#     # 列ごとの整形処理をapplyとlambdaで実施
#     df_tmp['商品ID'] = df_tmp['商品ID'].apply(lambda x: x[0][0] if isinstance(x, tuple) and isinstance(x[0], tuple) else x[0])
#     df_tmp['商品名'] = df_tmp['商品名'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
#     df_tmp['imgid'] = df_tmp['商品名'].apply(productname_to_imgid)
#     df_tmp['imgids'] = df_tmp['imgid'].apply(lambda x: [x] if x else [])
#     if "ウォッチリスト" in df_tmp: df_tmp['ウォッチリスト'] = df_tmp['ウォッチリスト'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
#     if "現在価格" in df_tmp: df_tmp['現在価格'] = df_tmp['現在価格'].apply(lambda x: int(x[0].replace(" 円", "")) if isinstance(x, tuple) and x[0] else None)
#     if "最高落札価格" in df_tmp: df_tmp['最高落札価格'] = df_tmp['最高落札価格'].apply(lambda x: int(x[0].replace(" 円", "")) if isinstance(x, tuple) and x[0] else None)
#     if "終了日時" in df_tmp: df_tmp['終了日時'] = df_tmp['終了日時'].apply(lambda x: datetime.strptime(f"{current_year}年{x[0]}", "%Y年%m月%d日 %H時%M分") if isinstance(x, tuple) and x[0] else None)
#     if "落札者" in df_tmp: df_tmp['落札者'] = df_tmp['落札者'].apply(lambda x: x[1].split("userID=")[-1] if isinstance(x, tuple) and x[1] else None)
#     if "最新のメッセージ" in df_tmp: df_tmp['navi'] = df_tmp['最新のメッセージ'].apply(lambda x: x[1] if isinstance(x, tuple) else None)
#     if "最新のメッセージ" in df_tmp: df_tmp['最新のメッセージ'] = df_tmp['最新のメッセージ'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
#     return df_tmp





def hash_url(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def cache_path(url: str) -> Path:
    hashed_url = hash_url(url)
    return Path(f"./cache/{hashed_url}.json")

def parse_status_from_class(class_name: str) -> TransactionStatus:
    if "current04" in class_name:
        return TransactionStatus.RECEIPT
    elif "current03" in class_name:
        return TransactionStatus.SHIPPING
    elif "current02" in class_name:
        return TransactionStatus.PAYMENT
    else:
        return TransactionStatus.INITIATED


def cache_status(func):
    @functools.wraps(func)
    def wrapper(cookies, url, *args, **kwargs):
        cache_file = cache_path(url)
        
        # Check for cached result
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            if cached_data['status'] == TransactionStatus.RECEIPT.name:
                return (
                    TransactionStatus[cached_data['status']],
                    cached_data['is_matome'],
                    cached_data['values'],
                    cached_data['matome_accept_url'],
                )
        
        # Call the original function
        result = func(cookies, url, *args, **kwargs)
        
        # Cache the result
        with open(cache_file, 'w') as f:
            json.dump({
                "status": result[0].name,
                "is_matome": result[1],
                "values": result[2],
                "matome_accept_url": result[3],
            }, f)
        
        return result
    
    return wrapper


def extract_input_values(soup):
    # 辞書に格納するための変数
    input_values = {}

    # 全ての<input>タグを取得
    inputs = soup.find_all('input')
    # 各<input>タグからidまたはnameとvalueを抽出
    for input_tag in inputs:
        # idが存在する場合はidを、ない場合はnameをキーとして使用
        input_key = input_tag.get('id') or input_tag.get('name')
        input_value = input_tag.get('value')
        if input_key:  # idまたはnameが存在する場合のみ格納
            input_values[input_key] = input_value

    return input_values



def extract_input_values_with_parent_form(soup):
    # 辞書に格納するための変数
    input_values = {}

    # 全ての<input>タグを取得
    inputs = soup.find_all('input')

    # 各<input>タグを処理
    for input_tag in inputs:
        # 親が<form>かどうか確認
        form_tag = input_tag.find_parent('form')

        if form_tag:  # 親が<form>の場合
            # form の action を取得してプレフィックスにする
            action_prefix = form_tag.get('action', '').lstrip('/')
        else:
            # 親が<form>でない場合はプレフィックスなし
            action_prefix = ''

        # idが存在する場合はidを、ない場合はnameをキーとして使用
        input_key = input_tag.get('id') or input_tag.get('name')
        input_value = input_tag.get('value')

        if input_key:  # idまたはnameが存在する場合のみ格納
            # actionをプレフィックスとしてキー名を作成
            full_key = f"{action_prefix}/{input_key}" if action_prefix else input_key
            input_values[full_key] = input_value

    return input_values




def display_images_in_single_row(files):
    """
    画像を1行1枚ずつJupyter Notebook上に表示する。
    
    :param files: 表示する画像ファイルのリスト
    """
    num_images = len(files)

    fig, axes = plt.subplots(num_images, 1, figsize=(10, 5 * num_images))  # 行数を画像数に設定
    if num_images == 1:  # 画像が1枚だけの場合はaxesをリストに変換
        axes = [axes]

    for idx, file in enumerate(files):
        img = Image.open(file)
        axes[idx].imshow(img)
        axes[idx].axis('off')  # 軸を非表示
        title = os.path.dirname(file).split("/")[-1]
        # title = os.path.basename(file)
        if title == "b":
            color = "green"
        else:
            color = "red"
            
        axes[idx].set_title(title, fontsize=14, color=color)  # フォントサイズを調整
    
    plt.tight_layout()
    plt.show()



class YahooAuctionTrade():
    def __init__(self, initial_cookies):
        # セッションを作成
        self.session = requests.Session()
        self.session.cookies.update(initial_cookies)
        self.session.max_redirects = 2
        # 過去のクッキーを保持しておき、保存の分岐に用いる
        self._temp_cookies = self.session.cookies.copy()

    def is_cookie_updated(self):
        return self._temp_cookies != self.session.cookies

    def get_table(self, url, index_col=0, table_class='ItemTable', referer='https://auctions.yahoo.co.jp/user/jp/show/mystatus', apg=None):
        """
        Yahoo!オークションのページからテーブルデータを取得し、次ページのapgを返す。
    
        :param cookies: リクエストに使用するクッキー
        :param url: リクエストURL
        :param index_col: テーブルのインデックス列（デフォルト: 0）
        :param table_class: 取得するテーブルのクラス名
        :param referer: ヘッダーのリファラー設定
        :param apg: 現在のページ番号
        :return: DataFrameと次のapg（存在しない場合はNone）
        """
        # `apg` が指定されていればURLに追加
        if apg is not None:
            url = f"{url}&apg={apg}"
    
        # ヘッダー情報
        headers = {
            'accept': '*/*',
            'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'origin': 'https://auctions.yahoo.co.jp',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': referer,
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-arch': '"arm"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.71", "Chromium";v="131.0.6778.71", "Not_A Brand";v="24.0.0.0"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"macOS"',
            'sec-ch-ua-platform-version': '"15.1.1"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
    
        # ページを取得
        response = self.session.get(url, headers=headers)
        assert response.status_code == 200, f"リクエスト失敗: {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
    
        # 次のページのapgを探す
        next_apg = None
        for a_tag in soup.find_all('a', href=True):
            match = re.search(r'apg=(\d+)', a_tag['href'])
            if match:
                next_page = int(match.group(1))
                if apg is None or next_page > apg:
                    next_apg = next_page
                    break
    
        # テーブルを取得
        try:
            tables = pd.read_html(StringIO(response.text), attrs={'class': table_class}, flavor='bs4', extract_links="body", index_col=index_col, header=0)
        except ValueError:
            return None, next_apg
    
        df_tmp = tables[0].dropna(how="all")
        df_tmp = df_tmp.reset_index()
    
        # DataFrameを辞書形式に変換
        data = df_tmp.to_dict(orient="records")
        
        df_tmp = pd.DataFrame([{key[0]: value for key, value in record.items()} for record in data])
        current_year = datetime.now().year
        
        # 列ごとの整形処理
        df_tmp['商品ID'] = df_tmp['商品ID'].apply(lambda x: x[0][0] if isinstance(x, tuple) and isinstance(x[0], tuple) else x[0])
        df_tmp['商品名'] = df_tmp['商品名'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
        df_tmp['imgid'] = df_tmp['商品名'].apply(productname_to_imgid)
        df_tmp['imgids'] = df_tmp['imgid'].apply(lambda x: [x] if x else [])
        if "ウォッチリスト" in df_tmp: df_tmp['ウォッチリスト'] = df_tmp['ウォッチリスト'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
        if "現在価格" in df_tmp: df_tmp['現在価格'] = df_tmp['現在価格'].apply(lambda x: int(x[0].replace(" 円", "")) if isinstance(x, tuple) and x[0] else None)
        if "最高落札価格" in df_tmp: df_tmp['最高落札価格'] = df_tmp['最高落札価格'].apply(lambda x: int(x[0].replace(" 円", "")) if isinstance(x, tuple) and x[0] else None)
        if "終了日時" in df_tmp: df_tmp['終了日時'] = df_tmp['終了日時'].apply(lambda x: datetime.strptime(f"{current_year}年{x[0]}", "%Y年%m月%d日 %H時%M分") if isinstance(x, tuple) and x[0] else None)
        if "落札者" in df_tmp: df_tmp['落札者'] = df_tmp['落札者'].apply(lambda x: x[1].split("userID=")[-1] if isinstance(x, tuple) and x[1] else None)
        if "最新のメッセージ" in df_tmp: df_tmp['navi'] = df_tmp['最新のメッセージ'].apply(lambda x: x[1] if isinstance(x, tuple) else None)
        if "最新のメッセージ" in df_tmp: df_tmp['最新のメッセージ'] = df_tmp['最新のメッセージ'].apply(lambda x: x[0] if isinstance(x, tuple) else None)
        
        return df_tmp, next_apg
    
    def fetch_all_pages(self, url, index_col=0, start_apg=1, max_pages=None):
        """
        指定されたURLから全てのページ、または最大ページ数までのテーブルデータを取得し、結合する。
    
        :param cookies: リクエストに使用するクッキー
        :param url: ベースURL
        :param index_col: テーブルのインデックス列（デフォルト: 0）
        :param start_apg: 開始するページ番号（デフォルト: 1）
        :param max_pages: 最大ページ数（デフォルト: None。指定がない場合、全ページを取得）
        :return: 全ページのデータを結合したDataFrame
        """
        combined_df = pd.DataFrame()
        current_apg = start_apg
        fetched_pages = 0
    
        while current_apg is not None:
            # 最大ページ数に達したら終了
            if max_pages is not None and fetched_pages >= max_pages:
                logger.info(f"Reached the maximum number of pages: {max_pages}")
                break
    
            logger.info(f"Fetching page {url} {current_apg}...")
            df, next_apg = self.get_table(url, index_col=index_col, apg=current_apg)
            
            if df is not None:
                combined_df = pd.concat([combined_df, df], ignore_index=True)
            
            current_apg = next_apg
            fetched_pages += 1
            time.sleep(SLEEP_TIME)
    
        return combined_df
    
    def get_closed_df(self, max_pages=2):
        url="https://auctions.yahoo.co.jp/closeduser/jp/show/mystatus?select=closed&hasWinner=1"
        return self.fetch_all_pages(url, index_col=0, max_pages=max_pages)

    @cache_status
    def get_status(self, url):
        # ヘッダーの設定
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": "https://auctions.yahoo.co.jp/",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-arch": '"arm"',
            "sec-ch-ua-full-version-list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-platform-version": '"15.1.1"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-site",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        
        # GETリクエスト
        time.sleep(SLEEP_TIME)  # スリープを追加
        logger.info(f"get status {url}")
        response = self.session.get(url, headers=headers, allow_redirects=True)
        assert response.status_code == 200, f"{response.status_code, response.text, response.headers}"
        
        # return response
        soup = BeautifulSoup(response.text, 'html.parser')
        values = extract_input_values_with_parent_form(soup)
        
        link = soup.find('a', class_='libBtnBlueL')
        if link is None:
            matome_accept_url = None
        elif "leavefeedback" in link['href']:
            matome_accept_url = None
        else:
            matome_accept_url = "https://contact.auctions.yahoo.co.jp"+link['href']
            
        # 指定された div 要素を取得
        div_element = soup.find("div", class_="acMdStatusImage")
        
        # 子要素 <ul> のクラスを取得
        ul_element = div_element.find("ul", class_="acMdStatusImage__status")
        
        # クラス名を取得
        class_name = ul_element.get("class")
        
        # クラス名をスペースで連結して文字列として表示
        class_name_str = " ".join(class_name)
        
        # 使用例
        class_name = class_name_str
        status = parse_status_from_class(class_name)
        return status, "ptsBundleItemBtn" in str(soup), values, matome_accept_url
    


    def get_matome_imgids(self, original_url: str, ):
        """
        Replace `/seller/top` in the URL with `/bundle/list` and make a GET request.

        Args:
            original_url (str): The original URL containing `/seller/top`.
            cookies (dict): Cookies to include in the request.

        Returns:
            Response: The response object from the GET request.
        """
        # Parse the URL
        parsed_url = urlparse(original_url)

        # Replace `/seller/top` with `/bundle/list`
        new_path = parsed_url.path.replace('/seller/top', '/bundle/list')

        # Create the new URL
        new_url = urlunparse(
            ParseResult(
                scheme=parsed_url.scheme,
                netloc=parsed_url.netloc,
                path=new_path,
                params=parsed_url.params,
                query=parsed_url.query,
                fragment=parsed_url.fragment
            )
        )

        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": original_url,
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-arch": '"arm"',
            "sec-ch-ua-full-version-list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-platform-version": '"15.1.1"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        # Make the GET request
        r = self.session.get(new_url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        dom = etree.HTML(str(soup))
        elements = dom.xpath('//*[@class="decItmName"]//a')
        ids = [productname_to_imgid(element.text) for element in elements]
        paths = [urlparse(element.get("href")).path.split('/')[-1] for element in elements if element.get("href")]

        return ids, paths


    def get_ship_preview(self, url):
        """
        URLからRefererヘッダーを作成し、GETリクエストを送信します。

        Args:
            cookies (dict): リクエストに使用するクッキー情報。
            url (str): リクエスト先のURL。

        Returns:
            requests.Response: GETリクエストのレスポンスオブジェクト。
        """
        assert isinstance(url, str)
        # URLを解析してRefererを作成
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        referer = f"https://contact.auctions.yahoo.co.jp/seller/top?aid={query_params.get('aid', [''])[0]}&syid={query_params.get('syid', [''])[0]}&bid={query_params.get('bid', [''])[0]}&oid={query_params.get('oid', [''])[0]}"

        # ヘッダーを構築
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "sec-ch-ua-arch": "\"arm\"",
            "sec-ch-ua-full-version-list": "\"Google Chrome\";v=\"131.0.6778.205\", \"Chromium\";v=\"131.0.6778.205\", \"Not_A Brand\";v=\"24.0.0.0\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": "\"\"",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-ch-ua-platform-version": "\"15.1.1\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "Referer": referer,
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        # GETリクエストを送信
        response = self.session.get(url, headers=headers)
        assert response.status_code == 200, f"{response.status_code, response.text}"
        soup = BeautifulSoup(response.text, 'html.parser')
        values = extract_input_values_with_parent_form(soup)
        return values


    def post_ship_preview(self, url, crumb):
        """
        URLから必要なデータを動的に生成し、POSTリクエストを送信します。

        Args:
            cookies (dict): リクエストに使用するクッキー情報。
            url (str): リクエストに必要なパラメータを含むURL。
            crumb (str): POSTデータに含めるcrumb値。

        Returns:
            requests.Response: POSTリクエストのレスポンスオブジェクト。
        """
        # URLを解析
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 必要なパラメータを取得
        oid = query_params.get("oid", [None])[0]
        syid = query_params.get("syid", [None])[0]
        aid = query_params.get("aid", [None])[0]
        bid = query_params.get("bid", [None])[0]

        if not all([oid, syid, aid, bid]):
            raise ValueError("URLに必要なパラメータが不足しています。")

        # POSTデータを生成
        data = {
            "shipUseParent": "1",
            "shippingMethod": "",
            "aid": aid,
            "syid": syid,
            "bid": bid,
            "oid": oid,
            "_crumb": crumb,
            "chargeForShipping": "0"
        }

        # ヘッダーを構築
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "sec-ch-ua-arch": "\"arm\"",
            "sec-ch-ua-full-version-list": "\"Google Chrome\";v=\"131.0.6778.205\", \"Chromium\";v=\"131.0.6778.205\", \"Not_A Brand\";v=\"24.0.0.0\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": "\"\"",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-ch-ua-platform-version": "\"15.1.1\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "Referer": url,
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }

        # POSTリクエストを送信
        response = self.session.post(
            "https://contact.auctions.yahoo.co.jp/seller/bundle/shippreview",
            headers=headers,
            data=data
        )
        assert response.status_code == 200, f"{response.status_code, response.text}"
        soup = BeautifulSoup(response.text, 'html.parser')
        values = extract_input_values_with_parent_form(soup)
        return values


    def post_ship_submit(self, url, crumb):
        """
        URLから必要なデータを動的に生成し、shipsubmit エンドポイントにPOSTリクエストを送信します。

        Args:
            cookies (dict): リクエストに使用するクッキー情報。
            url (str): リクエストに必要なパラメータを含むURL。
            crumb (str): POSTデータに含めるcrumb値。

        Returns:
            requests.Response: POSTリクエストのレスポンスオブジェクト。
        """
        # URLを解析
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 必要なパラメータを取得
        oid = query_params.get("oid", [None])[0]
        syid = query_params.get("syid", [None])[0]
        aid = query_params.get("aid", [None])[0]
        bid = query_params.get("bid", [None])[0]

        if not all([oid, syid, aid, bid]):
            raise ValueError("URLに必要なパラメータが不足しています。")

        # POSTデータを生成
        data = {
            "back": "",
            "aid": aid,
            "syid": syid,
            "bid": bid,
            "oid": oid,
            "_crumb": crumb,
            "shipUseParent": "1",
            "shippingMethod": "",
            "shipChargeNumber": "",
            "chargeForShipping": "0"
        }
        # return data

        # ヘッダーを構築
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "sec-ch-ua-arch": "\"arm\"",
            "sec-ch-ua-full-version-list": "\"Google Chrome\";v=\"131.0.6778.205\", \"Chromium\";v=\"131.0.6778.205\", \"Not_A Brand\";v=\"24.0.0.0\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": "\"\"",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-ch-ua-platform-version": "\"15.1.1\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "Referer": "https://contact.auctions.yahoo.co.jp/seller/bundle/shippreview",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }

        # POSTリクエストを送信
        response = self.session.post(
            "https://contact.auctions.yahoo.co.jp/seller/bundle/shipsubmit",
            headers=headers,
            data=data
        )
        assert response.status_code == 200, f"{response.status_code, response.text}"
        return response



    def send_message(self, url, message, crumb):
        """
        指定されたURL、メッセージ、crumbを使用してPOSTリクエストを送信する関数。

        Args:
            url (str): 送信先のURL。
            message (str): 送信するメッセージ内容。
            crumb (str): CSRF保護のためのcrumbトークン。

        Returns:
            dict: ステータスコードとレスポンスの内容。
        """
        # URLのパラメータを解析して必要な情報を取得
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # 必要なパラメータを取得
        oid = query_params.get("oid", [None])[0]
        syid = query_params.get("syid", [None])[0]
        aid = query_params.get("aid", [None])[0]
        bid = query_params.get("bid", [None])[0]

        if not all([oid, syid, aid, bid]):
            raise ValueError("URLに必要なパラメータが不足しています。")

        # リクエストヘッダー
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://contact.auctions.yahoo.co.jp",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": url,
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-arch": "arm",
            "sec-ch-ua-full-version-list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": "",
            "sec-ch-ua-platform": "macOS",
            "sec-ch-ua-platform-version": "15.1.1",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }

        # データ
        data = {
            "oid": oid,
            "syid": syid,
            "aid": aid,
            "bid": bid,
            "crumb": crumb,
            "body": message,
        }
        # リクエストを送信
        response = self.session.post("https://contact.auctions.yahoo.co.jp/message/submit", headers=headers, data=data)
        assert response.status_code == 200, f"{response.status_code, response.text}"
        return response


    def request_ready_shippment(self, referer_url, _crumb):
        # Referer URLからクエリパラメータを抽出
        parsed_url = urlparse(referer_url)
        query_params = parse_qs(parsed_url.query)

        # 必要なパラメータを準備
        aid = query_params.get("aid", [None])[0]
        syid = query_params.get("syid", [None])[0]
        bid = query_params.get("bid", [None])[0]
        oid = query_params.get("oid", [None])[0]

        if not all([aid, syid, bid, oid]):
            raise ValueError("URLから必要なパラメータを抽出できませんでした。")

        # ヘッダーを設定
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ja,en-US;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://contact.auctions.yahoo.co.jp",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": referer_url,
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-arch": "arm",
            "sec-ch-ua-full-version-list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-platform-version": '"15.1.1"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        # POSTデータを設定
        data = {
            "aid": aid,
            "syid": syid,
            "bid": bid,
            "oid": oid,
            ".crumb": _crumb,
            "baggHandling1": "",
            "baggHandling2": "",
            "shipItemName": "",
        }
        
        # POSTリクエストを送信
        response = self.session.post(
            "https://contact.auctions.yahoo.co.jp/seller/ready",
            headers=headers,
            data=data,
        )
        assert response.status_code == 200, f"{response.status_code, response.text}"
        return response


    def request_complete_shippment(self, url, _crumb, ):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # 必要なパラメータを準備
        aid = query_params.get("aid", [None])[0]
        syid = query_params.get("syid", [None])[0]
        bid = query_params.get("bid", [None])[0]
        oid = query_params.get("oid", [None])[0]

        if not all([aid, syid, bid, oid]):
            raise ValueError("URLから必要なパラメータを抽出できませんでした。")

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'priority': 'u=0, i',
            'referer': url,
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-arch': '"arm"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"macOS"',
            'sec-ch-ua-platform-version': '"15.1.1"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        params = {
            "aid": aid,
            "syid": syid,
            "bid": bid,
            "oid": oid,
            ".crumb": _crumb,
            'shipInvoiceNumReg': '1',
        }
        
        response = self.session.get(
            'https://contact.auctions.yahoo.co.jp/seller/submit',
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"{response.status_code, response.text}"
        return response


    def shipping_print_code(self, crumb_list, navi_list, img_paths, gift_list=[]):
        # 何番目の取引に発送するか
        main_idx=0
        crumb = crumb_list[main_idx]
        url = navi_list[main_idx]
        message = generate_message(img_paths, navi_list, gift_list)
        response = self.send_message(url, message, crumb)
        assert response.status_code == 200, f"{response.status_code, response.text}"
        return response

    def accept_omatome(self, url):
        status, is_matome, values, matome_accept_url = self.get_status(url)
        if matome_accept_url:
            values1 = self.get_ship_preview(matome_accept_url)
            time.sleep(10)
            values2 = self.post_ship_preview(url, values1['seller/bundle/shippreview/_crumb'])
            time.sleep(10)
            ret_submit = self.post_ship_submit(url, values2['seller/bundle/shipsubmit/_crumb'])    
            time.sleep(10)
            return True
        else:
            return False


    def ship(self, gift_image_candidates=None):
        # 売却済み一覧
        trades = self.get_closed_df()

        df = trades.copy()
        # 不要な列を削除し、状態を更新
        df = df.drop(columns=['取引', '操作', "選択"])
        df = df.dropna(subset=['navi'])
        df['status'], df['is_matome'], df["values"], df["matome_accept_url"] = zip(*df['navi'].apply(lambda url: self.get_status(url)))
        df['status_value'] = df['status'].apply(lambda x: x.value if hasattr(x, 'name') else x)
        df2 = df[df['status'] != TransactionStatus.RECEIPT]


        # まとめ取引の画像を集約
        # df2をコピーしてdf3を作成
        df3 = df2.copy()
        
        # is_matomeがTrueの場合のみ、get_matome_imgidsを呼び出し、結果を適切に処理
        def process_row(row):
            if row["is_matome"]:
                imgids, paths = self.get_matome_imgids(row["navi"])
                imgids = list(set(row["imgids"] + imgids)) if row["imgids"] else imgids
            else:
                imgids = row["imgids"]
                paths = [row["商品ID"]]
            return pd.Series({"imgids": imgids, "paths": paths})

        df3[["imgids", "paths"]] = df3.apply(process_row, axis=1)
        def calculate_total_price_with_error(paths, trades):
            if not paths:  # pathsが空の場合
                return 0
            # pathsから商品IDを抽出
            product_ids = [path.split('/')[-1] for path in paths]
            # 商品IDがtradesに存在しない場合、例外を発生
            missing_ids = set(product_ids) - set(trades["商品ID"])
            assert not missing_ids, f"商品IDが見つかりません: {missing_ids}"
            # 合計価格を計算
            return trades.loc[trades["商品ID"].isin(product_ids), "最高落札価格"].sum()
        
        # total_priceカラムを追加
        df3["total_price"] = df3["paths"].apply(lambda paths: calculate_total_price_with_error(paths, trades))
        
        df3["落札数"] = df3["imgids"].apply(len)
        df3[["商品ID", "落札者", "最新のメッセージ", "imgids", "status", "落札数", "total_price"]]

        
        df4 = df3.copy()
        
        aggregated = df4.groupby('落札者').agg(
            num_transactions=('商品ID', 'count'),
            imgid_list=('imgids', lambda x: list(itertools.chain.from_iterable(x))),
            status_list=('status', list),
            navi_list=('navi', list),
            num_images=("落札数", "sum"),
            total_price=("total_price", "sum"),
            crumb_list=('values', lambda x: [i["crumb"] for i in x]),
            ready_crumb_list=('values', lambda x: [i.get("seller/ready/.crumb") for i in x]),
            submit_crumb_list=('values', lambda x: [i.get("seller/submit/.crumb") for i in x])
        ).reset_index()
        
        # 発送可能かを判定（全てのステータスが SHIPPING であるか）
        aggregated['is_shippable'] = aggregated['status_list'].apply(
            lambda statuses: all(status == TransactionStatus.SHIPPING for status in statuses)
        )
        aggregated['img_paths'] = aggregated['imgid_list'].apply(
            lambda imgids: [f"./data/items/{i.split('_')[0]}/{i}_submission.jpg" for i in imgids]
        )
        aggregated['valid_paths'] = aggregated['img_paths'].apply(
            lambda paths: all(os.path.exists(path) for path in paths)
        )
        assert aggregated['valid_paths'].all(), "一部の画像パスが存在しません。"
        aggregated['num_gift_images'] = aggregated['total_price'].apply(
            lambda total_price: total_price//2500
        )

        aggregated['gift_images'] = aggregated['num_gift_images'].apply(
            lambda num_gift_images: gift_image_candidates[:num_gift_images] if gift_image_candidates else []
        )


        shippable = aggregated[aggregated["is_shippable"]]
        
        for user, status_list, navi_list, is_shippable in aggregated[["落札者", "status_list", "navi_list", "is_shippable"]].values.tolist():
            if is_shippable:
                flag = "発送可能✅"
            else:
                flag = "発送保留❌"
        
            logger.info(f"{flag} : {user} :")
            for status, url in zip(status_list, navi_list):
                logger.info(f"  * {status.name} : {url}")
        
        logger.info("aggregated\n"+aggregated[["落札者", "num_transactions", "num_images", "is_shippable", "valid_paths", "total_price", "num_gift_images"]].to_string(index=False))
        
        for _, row in shippable.iterrows():
            logger.info(f"落札者: {row['落札者']} ({row['num_images']})")
            navi_list = row['navi_list']
            crumb_list = row['crumb_list']
            ready_crumb_list = row['ready_crumb_list']
            submit_crumb_list = row['submit_crumb_list']
            img_paths = row['img_paths']
            total_price = row['total_price']
            gift_images = row['gift_images']

            # プリントコード発行
            r = self.shipping_print_code(crumb_list, navi_list, img_paths, gift_images)
            logger.info("プリントコードを送信しました")
            
            # 発送コード発行
            for url, ready_crumb, submit_crumb in zip(navi_list, ready_crumb_list, submit_crumb_list):
                logger.info(f"発送処理中: {url}")
                r1 = self.request_ready_shippment(url, ready_crumb)
                time.sleep(10)
                r2 = self.request_complete_shippment(url, submit_crumb)
                assert r1.status_code == 200 and r2.status_code == 200, (r1.status_code, r2.status_code)
                time.sleep(10)
            logger.info("発送処理完了")
            logger.info("-" * 40)
            logger.info("")



def calculate_chunks_length(total_length, max_size=23):
    return math.ceil(total_length / max_size)


def generate_message(img_paths, navi_list, gift_list=[]):
    # assert len(gift_list)==0, "プレゼント画像は未実装です"
    qrcode_image = img2url_multi(img_paths, gift_list=gift_list)
    print_manual_image = "https://i.imghippo.com/files/EJn4438nFk.png"
    
    # まとめメッセージを条件によって定義
    if len(navi_list) >= 2:
        navi_text = "・" + "\n・".join(navi_list)
        summary_message = f"""
以下の取引 {len(navi_list)} 件まとめてのご案内となります。
他の取引ナビでのご連絡は省略しておりますので、ご了承ください。

{navi_text}
"""
    else:
        summary_message = ""

    if len(gift_list)>0:
        gift_message = """
なお、多くのご購入に感謝し、未出品の画像を特典としてお付けしました。プリントにてぜひご確認いただき、お楽しみいただければ幸いです。"""
    else:
        gift_message = ""

    # メッセージを組み立て
    message = f"""
このたびはご購入およびお支払い、誠にありがとうございます。商品 {len(img_paths)} 件分のプリントコードを発行しましたので、お知らせします。
{summary_message}
本連絡をもちまして、発送完了のご案内とさせていただきます。プリント後は、お手数ですが受け取り連絡をお願いします。
{gift_message}
改めまして、この度はお取引いただきありがとうございました！

※商品の特性上、こちらからの評価は控えさせていただきます。また、当方への評価も不要ですので、どうぞお気遣いなくお願いいたします

{qrcode_image}
{print_manual_image}
"""
    return message




def display_resized_images_horizontally(files, max_images_per_row=5):
    """
    画像を横一列または複数列に並べてJupyter Notebook上に表示する。
    
    :param files: 表示する画像ファイルのリスト
    :param max_images_per_row: 1行に表示する最大画像数
    """
    num_images = len(files)
    num_rows = (num_images + max_images_per_row - 1) // max_images_per_row  # 行数を計算

    fig, axes = plt.subplots(num_rows, max_images_per_row, figsize=(15, 3 * num_rows))
    axes = axes.ravel()  # 軸を1次元配列化して扱いやすくする

    for idx, file in enumerate(files):
        img = Image.open(file)
        axes[idx].imshow(img)
        axes[idx].axis('off')  # 軸を非表示
        axes[idx].set_title(file, fontsize=8)  # 小さいフォントでタイトルを設定
    
    # 余分な空のサブプロットを非表示にする
    for idx in range(num_images, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    plt.show()


def cache_to_csv(cache_dir="./cache"):
    """
    キャッシュデコレータ。関数の2番目の引数（年月）が現在の月の場合はキャッシュを使用しない。

    Args:
        cache_dir (str): キャッシュを保存するディレクトリのパス。
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) < 2:
                raise ValueError("2番目の引数（年月）が必要です。")
            key = args[1]  # 年月
            current_year_month = datetime.now().strftime("%Y%m")  # 現在の年月
            cache_file = os.path.join(cache_dir, f"{key}.csv")
            
            # 現在の月の場合はキャッシュを使用せずに実行
            if key == current_year_month:
                print(f"現在の月 ({current_year_month}) のためキャッシュを使用しません。")
                result = func(*args, **kwargs)
            # 過去の月の場合
            elif os.path.exists(cache_file):
                print(f"キャッシュからデータを読み込みます: {cache_file}")
                df = pd.read_csv(cache_file, index_col=0)  # index_col=0でインデックスを復元
                df["取扱日"] = pd.to_datetime(df["取扱日"])
                return df
                
            else:
                result = func(*args, **kwargs)
                if not isinstance(result, pd.DataFrame):
                    raise ValueError("戻り値は pandas.DataFrame である必要があります。")
                result.to_csv(cache_file, index=True)  # index=Trueでインデックスを保存
                print(f"データをキャッシュに保存しました: {cache_file}")
            return result

        return wrapper
    return decorator

@cache_to_csv()
def get_sales(cookies, datestr,):
    # ベースヘッダー
    base_headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "ja,en-US;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-arch": '"arm"',
        "sec-ch-ua-full-version-list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-model": '""',
        "sec-ch-ua-platform": '"macOS"',
        "sec-ch-ua-platform-version": '"15.1.1"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }
    
    # GETリクエスト用ヘッダー
    get_headers = base_headers.copy()
    get_headers.update({
        "Referer": "https://auctions.yahoo.co.jp/",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    })
    
    # GETリクエストを送信
    response = requests.get("https://salesmanagement.yahoo.co.jp/list", headers=get_headers, cookies=cookies)
    assert response.status_code == 200, f"{response.status_code, response.text}"
    
    soup = BeautifulSoup(response.text, "html.parser")
    input_values = extract_input_values(soup)
    crumb = input_values[".crumb"]
    
    post_headers = base_headers.copy()
    post_headers.update({
        "content-type": "application/x-www-form-urlencoded",
        "Referer": "https://salesmanagement.yahoo.co.jp/list",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "sec-fetch-site": "same-origin",
    })
    
    data = {
        "i": datestr,
        ".crumb": crumb,
    }
    
    # POSTリクエスト送信
    response = requests.post("https://salesmanagement.yahoo.co.jp/salesmanagelist_csv", headers=post_headers, data=data, cookies=cookies)
    assert response.status_code == 200, f"{response.status_code, response.text}"
    
    
    # ダウンロードしたバイナリデータ（例として代入）
    binary_data = response.content
    
    # Shift-JISでデコード
    decoded_data = binary_data.decode("shift_jis")
    
    # 各行を split して 10 列目までに制限
    truncated_rows = [row.split(',')[:10] for row in decoded_data.splitlines()]
    
    # 再び CSV 文字列として連結
    corrected_csv_data = "\n".join([",".join(cols) for cols in truncated_rows])
    
    # pandasで読み込み
    df = pd.read_csv(StringIO(corrected_csv_data))
    df
    df.set_index("商品ID", inplace=True)
    df["取扱日"] = pd.to_datetime(df["取扱日"], format="%Y年%m月%d日 %H時%M分", errors="coerce")
    num_cols = ["売上", "決済金額", "落札システム利用料", "販売手数料", "送料", "受取金額"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("取扱日")
    df["利益"] = df["売上"] - df["落札システム利用料"]
    df
    return df
