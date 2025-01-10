from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os
import json



# 認証プロセス
def authenticate():
    # 認証リクエスト
    auth_url = 'https://networkprint.ne.jp/LiteServer/app/login'
    auth_data = {
        'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    auth_response = requests.post(auth_url, data=auth_data)
    if auth_response.status_code != 200:
        print("認証失敗")
        print("Response:", auth_response.text)
        return
    
    # 認証レスポンスからトークンを取得
    return auth_response.json()
    return auth_token


def upload_file(file_path, token):
    register_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_path)[1].lower()

    multipart_data = MultipartEncoder(
        fields={
            'file': (register_name, open(file_path, 'rb'), 'image/jpeg'),
            'authToken': token,
            'registerName': register_name
        },
        boundary='----WebKitFormBoundary21zZxMEA7OXiANL6'
    )
    
    headers = {
        'Content-Type': multipart_data.content_type,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    url = 'https://networkprint.ne.jp/LiteServer/app/upload'
    response = requests.post(url, headers=headers, data=multipart_data)
    assert response.json().get("result") == ""


def create_print_sheet(image, expire_date):
    # 設定
    font_path = "./material/NotoSansCJK-Regular.ttc"  # フォントパス
    text = f"有効期限:  {expire_date}"

    font_size = 13  # 固定フォントサイズ
    
    original_width, original_height = image.size
    
    # フォント読み込み
    font = ImageFont.truetype(font_path, font_size)
    
    # テキストサイズ計算
    dummy_draw = ImageDraw.Draw(image)
    text_width, text_height = dummy_draw.textbbox((0, 0), text, font=font)[2:]
    
    # テキスト描画 (元画像に直接描画)
    draw = ImageDraw.Draw(image)
    text_x = (original_width - text_width) // 2 
    text_y = original_height - text_height  # 下部に描画
    draw.text((text_x, text_y), text, fill="black", font=font)
    
    # 追加画像の読み込み
    extra_image = Image.open("./material/print_manual-2.png")
    extra_width, extra_height = extra_image.size
    
    # 元画像を追加画像の幅に合わせてリサイズ
    scale_factor = extra_width / original_width
    resized_image = image.resize((extra_width, int(original_height * scale_factor)))
    resized_width, resized_height = resized_image.size
    
    # 新しいキャンバスの高さを計算 (追加画像 + リサイズ済み元画像)
    padding = 20
    new_height = resized_height + extra_height + padding
    
    # 新しいキャンバスを作成
    new_image = Image.new("RGB", (extra_width, new_height), "white")
    new_image.paste(resized_image, (0, 0))
    
    # 追加画像をキャンバスに貼り付け
    new_image.paste(extra_image, (0, resized_height + padding))
    
    # 保存と表示
    # new_image.save(save_path)
    return new_image


def get_qrcode(files, token):
    assert len(files) < 24

    for f in files:
        upload_file(f, token)
    
    url = 'https://networkprint.ne.jp/LiteServer/app/files'
    response_upload = requests.post(url, data={'authToken': token})
    assert response_upload.json()["result"] == ""
        
    # get QR code
    url = 'https://networkprint.ne.jp/nwpsapi/v1/login/qrcode'
    response_qr = requests.get(url, headers={"x-nwpstoken": token})
        
    image = Image.open(BytesIO(response_qr.content))
    return image, response_upload.json()

def edit_qrcode(qr_data, user_code, expire_date):
    font_path = "./material/NotoSansCJK-Regular.ttc"  # フォントのパス
    font_size1 = 45  # user_code 用のフォントサイズ（大きく設定）
    font_size2 = 17  # expire_date 用のフォントサイズ
    padding = 20  # 画像の余白
    text_padding = 10  # QRコードとテキスト間の余白
    corner_radius = 20  # 丸角の半径
    background_color = (255, 255, 255, 255)  # 背景色（白）
    text_color = (0, 0, 0, 255)  # テキスト色（黒）
    
    
    # --- フォントの読み込み ---
    font1 = ImageFont.truetype(font_path, font_size1)  # user_code 用フォント
    font2 = ImageFont.truetype(font_path, font_size2)  # expire_date 用フォント
    
    # --- テキストの準備 ---
    text1 = user_code
    text2 = f"プリント期限　 {expire_date}"
    
    # --- テキストサイズの計測 ---
    # ダミー画像を作成して ImageDraw オブジェクトを取得
    dummy_img = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy_img)
    
    # テキスト1（user_code）のバウンディングボックスを取得
    bbox1 = draw_dummy.textbbox((0, 0), text1, font=font1)
    text_width1 = bbox1[2] - bbox1[0]
    text_height1 = bbox1[3] - bbox1[1]
    
    # テキスト2（expire_date）のバウンディングボックスを取得
    bbox2 = draw_dummy.textbbox((0, 0), text2, font=font2)
    text_width2 = bbox2[2] - bbox2[0]
    text_height2 = bbox2[3] - bbox2[1]
    
    # --- サイズ計算 ---
    qr_width, qr_height = qr_data.size
    
    # 新しい画像のサイズを計算
    new_width = max(qr_width, text_width1, text_width2) + padding * 2
    new_height = padding + qr_height + text_padding + text_height1 + text_height2 + padding
    new_image = Image.new("RGBA", (new_width, new_height), background_color)
    
    # --- 丸角のマスク作成 ---
    mask = Image.new("L", new_image.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(0, 0), new_image.size], corner_radius, fill=255)
    new_image.putalpha(mask)
    
    # --- QRコードを中央に貼り付け ---
    qr_x = (new_width - qr_width) // 2
    qr_y = padding
    new_image.paste(qr_data, (qr_x, qr_y), qr_data)
    
    # --- テキストを描画 ---
    draw = ImageDraw.Draw(new_image)
    
    # テキスト1（user_code）の位置計算
    text1_x = (new_width - text_width1) // 2
    qr_height = qr_height-30
    text1_y = qr_y + qr_height + text_padding
    draw.text((text1_x, text1_y), text1, font=font1, fill=text_color)
    
    # テキスト2（expire_date）の位置計算
    text2_x = (new_width - text_width2) // 2
    text2_y = text1_y + text_height1 + 30  # テキスト1の下に5ピクセル余白
    draw.text((text2_x, text2_y), text2, font=font2, fill=text_color)
    
    return new_image


def upload_image_to_imghippo(api_key, image, title=""):
    """
    Imghippo API v1を使用して画像をアップロードします。

    Args:
        api_key (str): APIキー。
        image (PIL.Image.Image): アップロードする画像オブジェクト。
        title (str, optional): 画像のタイトル（任意）。

    Returns:
        dict: アップロード結果のJSONレスポンス。
    """
    # APIのエンドポイントURL
    url = "https://api.imghippo.com/v1/upload"  # 実際のAPIエンドポイントに置き換えてください

    try:
        # QRコードデータをBytesIOに保存
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        # POSTリクエストを送信
        response = requests.post(
            url,
            files={"file": ("qr_code.png", image_bytes, "image/png")},
            data={"title": title, "api_key": api_key},
        )

        # ステータスコードで成功/失敗を確認
        if response.status_code == 200 and response.json()["status"] == 200:
            # print("アップロード成功:")
            pass
        else:
            print(f"アップロード失敗: ステータスコード {response.status_code, response.json()}")
        return response

    except Exception as e:
        print(f"エラー: {e}")
        return None

def img2url(files, hippo_api_key="f7342f8a581c9e66888914bd1fc2a105"):
    assert len(files) < 24
    auth_token = authenticate()
    token = auth_token["authToken"]
    usercode = auth_token["userCode"]
    
    qr_data, response_data = get_qrcode(files, token)
    expire_date = response_data['files'][0]['deleteAt']
    assert len(response_data["files"]) == len(files)
    
    # 保存先ディレクトリの作成
    save_dir = "./print_qr"
    os.makedirs(save_dir, exist_ok=True)
    
    # QRコード画像の保存
    file_name = os.path.join(save_dir, f"{usercode}.png")
    qr_data.save(file_name)
    qr_data = qr_data.convert("RGBA")
    
    # QRコード編集
    new_image = edit_qrcode(qr_data, usercode, expire_date)
    
    # JSONデータ作成と保存
    json_data = {
        "files": files,
        "response_data": response_data
    }
    json_file_name = os.path.join(save_dir, f"{usercode}.json")
    with open(json_file_name, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    
    # QRコード画像をアップロード
    r = upload_image_to_imghippo(hippo_api_key, new_image)
    
    return r.json()["data"]["view_url"]

def split_list(input_list, max_size = 23):
    """
    リストを指定された上限に従って複数のリストに分割する関数。
    
    Args:
        input_list (list): 分割する対象のリスト。
        max_size (int): 各リストの最大サイズ。
        
    Returns:
        list of list: 分割されたリストのリスト。
    """
    # 分割されたリストを格納する
    result = []
    
    # 元のリストを走査しながら分割
    for i in range(0, len(input_list), max_size):
        result.append(input_list[i:i + max_size])
    
    return result

def edit_qrcodes(qr_data_list, user_code_list, expire_date):
    assert len(qr_data_list) == len(user_code_list), "QRコードとユーザコードのリストは同じ長さである必要があります。"
    
    font_path = "./material/NotoSansCJK-Regular.ttc"  # フォントのパス
    font_size1 = 14  # user_code 用のフォントサイズ
    font_size2 = 17  # expire_date 用のフォントサイズ
    font_size3 = 30  # 枚数表示用のフォントサイズ
    padding = 20  # 画像の余白
    text_padding = -35  # QRコードとテキスト間の余白
    count_padding = - 340
    vertical_spacing = 10  # 各QRコード間の間隔
    corner_radius = 20  # 丸角の半径
    background_color = (255, 255, 255, 255)  # 背景色（白）
    text_color = (0, 0, 0, 255)  # テキスト色（黒）
    
    # フォントの読み込み
    font1 = ImageFont.truetype(font_path, font_size1)
    font2 = ImageFont.truetype(font_path, font_size2)
    font3 = ImageFont.truetype(font_path, font_size3)
    
    # 各QRコードとユーザコードのサイズを計測
    dummy_img = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy_img)
    
    max_qr_width = max([qr.size[0] for qr in qr_data_list])
    max_text_width1 = max([draw_dummy.textbbox((0, 0), user_code, font=font1)[2] for user_code in user_code_list])
    expire_text_width = draw_dummy.textbbox((0, 0), f"プリント期限　 {expire_date}", font=font2)[2]
    text_width = max(max_text_width1, expire_text_width)
    
    total_height = padding
    for qr in qr_data_list:
        total_height += font_size3 + qr.size[1] + text_padding + font_size1 + vertical_spacing
    total_height += font_size2 + padding  # 最後の有効期限を追加
    
    new_width = max(max_qr_width, text_width) + padding * 2
    new_image = Image.new("RGBA", (new_width, total_height), background_color)
    
    # 丸角マスク
    mask = Image.new("L", new_image.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(0, 0), new_image.size], corner_radius, fill=255)
    new_image.putalpha(mask)
    
    draw = ImageDraw.Draw(new_image)
    current_y = padding
    
    # QRコードとユーザコードを描画
    for index, (qr, user_code) in enumerate(zip(qr_data_list, user_code_list), start=1):

        # QRコード描画
        qr_x = (new_width - qr.size[0]) // 2
        new_image.paste(qr, (qr_x, current_y), qr)
        current_y += qr.size[1]
        
        # ユーザコード描画
        text1_x = (new_width - draw_dummy.textbbox((0, 0), user_code, font=font1)[2]) // 2
        text1_y = current_y + text_padding
        draw.text((text1_x, text1_y), user_code, font=font1, fill=text_color)
        current_y += font_size1 + vertical_spacing

        # 枚数表示
        count_text = f"{index} / {len(qr_data_list)}"
        count_text_width = draw_dummy.textbbox((0, 0), count_text, font=font3)[2]
        count_text_x = (new_width - count_text_width) // 2
        draw.text((count_text_x, current_y + count_padding), count_text, font=font3, fill=text_color)
        current_y += font_size3 + text_padding  # 枚数表示分の高さ調整

    
    # 有効期限を描画
    expire_text = f"プリント期限　 {expire_date}"
    text2_x = (new_width - expire_text_width) // 2
    text2_y = current_y
    draw.text((text2_x, text2_y), expire_text, font=font2, fill=text_color)
    
    return new_image
    

def img2url_multi(file_lists, hippo_api_key="f7342f8a581c9e66888914bd1fc2a105"):
    filess = split_list(file_lists)
    qr_datas, usercodes, expire_dates = [], [], []
    for files in filess:
        auth_token = authenticate()
        token = auth_token["authToken"]
        usercode = auth_token["userCode"]
        
        qr_data, response_data = get_qrcode(files, token)
        expire_date = response_data['files'][0]['deleteAt']
        assert len(response_data["files"]) == len(files)
        
        # 保存先ディレクトリの作成
        save_dir = "./print_qr"
        os.makedirs(save_dir, exist_ok=True)
        
        # QRコード画像の保存
        file_name = os.path.join(save_dir, f"{usercode}.png")
        qr_data.save(file_name)
        qr_data = qr_data.convert("RGBA")

        qr_datas.append(qr_data)
        usercodes.append(usercode)
        expire_dates.append(expire_date)
    
    # QRコード編集
    new_image = edit_qrcodes(qr_datas, usercodes, expire_dates[0])
    
    # JSONデータ作成と保存
    json_data = {
        "files": files,
        "response_data": response_data
    }
    json_file_name = os.path.join(save_dir, f"{usercode}.json")
    with open(json_file_name, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    
    # QRコード画像をアップロード
    r = upload_image_to_imghippo(hippo_api_key, new_image)
    return r.json()["data"]["view_url"]


if __name__ == "__main__":
    # 使用例
    hippo_api_key = "f7342f8a581c9e66888914bd1fc2a105"
    files = ["./material/size.jpg"] * 2
    url = img2url(hippo_api_key, files)
    url
