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


def upload_image_to_imghippo(image, title=""):
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
    from dotenv import load_dotenv
    load_dotenv()

    url = "https://api.imghippo.com/v1/upload"  # 実際のAPIエンドポイントに置き換えてください
    # もし環境変数が指定されていなければエラー
    api_key=os.getenv("IMGHIPPO_API_KEY")
    if api_key is None:
        raise HippoError("Imghippo API キーが設定されていません。")

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
        return response.json()["data"]["view_url"]

    except Exception as e:
        raise HippoError(f"Imghippo API へのアップロードに失敗しました: {e}") from None

def edit_present_qrcode(qr_data, user_code, expire_date):
    font_path = "./material/NotoSansCJK-Regular.ttc"  # 通常フォントのパス
    font_path_bold = "./material/NotoSansCJK-Bold.ttc"  # 太文字フォントのパス
    font_size1 = 14  # user_code 用のフォントサイズ
    font_size2 = 17  # expire_date 用のフォントサイズ
    font_size_header = 20  # プレゼントコード用フォントサイズ
    padding = 20  # 画像の余白
    text_padding = -20  # QRコードとテキスト間の余白
    header_padding = 20  # 上部テキスト用の余白
    header_height = 40  # ヘッダーエリアの高さ
    corner_radius = 20  # 丸角の半径
    border_size = 6  # 枠線の厚さ
    text_color = (0, 0, 0, 255)  # テキスト色（黒）
    fill_color = (255, 255, 255, 255)  # 塗りつぶし色（白）
    text_header_color = fill_color
    
    # --- フォントの読み込み ---
    font1 = ImageFont.truetype(font_path, font_size1)  # user_code 用フォント
    font2 = ImageFont.truetype(font_path, font_size2)  # expire_date 用フォント
    font_header = ImageFont.truetype(font_path_bold, font_size_header)  # 上部テキスト用フォント
    
    # --- テキストの準備 ---
    text_header = "プレゼント コード"
    text_header = "いつもご利用ありがとうございます"
    text1 = user_code
    text2 = f"プリント期限　 {expire_date}"
    
    # --- テキストサイズの計測 ---
    dummy_img = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy_img)
    
    bbox_header = draw_dummy.textbbox((0, 0), text_header, font=font_header)
    text_width_header = bbox_header[2] - bbox_header[0]
    text_height_header = bbox_header[3] - bbox_header[1]
    
    bbox1 = draw_dummy.textbbox((0, 0), text1, font=font1)
    text_width1 = bbox1[2] - bbox1[0]
    text_height1 = bbox1[3] - bbox1[1]
    
    bbox2 = draw_dummy.textbbox((0, 0), text2, font=font2)
    text_width2 = bbox2[2] - bbox2[0]
    text_height2 = bbox2[3] - bbox2[1]
    
    # --- サイズ計算 ---
    qr_width, qr_height = qr_data.size
    content_width = max(qr_width, text_width1, text_width2, text_width_header)
    content_height = (
        header_height  # ヘッダーエリアの高さ
        + qr_height
        + text_padding
        + text_height1
        + text_height2
    )
    new_width = content_width + padding * 2 + border_size * 2
    new_height = content_height + padding * 2 + border_size * 2
    
    # --- 背景グラデーションを作成 ---
    gradient = Image.new("RGBA", (new_width, new_height))
    draw_gradient = ImageDraw.Draw(gradient)
    start_color = (100, 125, 245)  # #647DF5
    end_color = (65, 192, 217)    # #41C0D9
    for x in range(new_width):
        ratio = x / new_width
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        draw_gradient.line([(x, 0), (x, new_height)], fill=(r, g, b, 255))
    
    # --- 枠線用マスクを作成 ---
    mask = Image.new("L", (new_width, new_height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle(
        [(0, 0), (new_width, new_height)],
        corner_radius,
        fill=255
    )
    gradient.putalpha(mask)
    
    # --- 内側の白い塗りつぶしを作成 ---
    inner_width = new_width - 2 * border_size
    inner_height = new_height - 2 * border_size - header_height  # ヘッダー分高さを減らす
    inner_image = Image.new("RGBA", (inner_width, inner_height), fill_color)
    mask_inner = Image.new("L", (inner_width, inner_height), 0)
    draw_inner = ImageDraw.Draw(mask_inner)
    draw_inner.rounded_rectangle(
        [(0, 0), (inner_width, inner_height)],
        corner_radius - border_size,  # 内側の角半径を調整
        fill=255
    )
    inner_image.putalpha(mask_inner)
    
    # --- 内側の白い塗りつぶしを貼り付け ---
    gradient.paste(inner_image, (border_size, header_height + border_size), inner_image)
    
    # --- QRコードを中央に貼り付け ---
    qr_x = (new_width - qr_width) // 2
    qr_y = header_height + padding + border_size
    gradient.paste(qr_data, (qr_x, qr_y), qr_data)
    
    # --- テキストを描画 ---
    draw = ImageDraw.Draw(gradient)
    
    # ヘッダーエリア
    text_header_x = (new_width - text_width_header) // 2
    text_header_y = (header_height - text_height_header) // 2
    draw.text((text_header_x, text_header_y), text_header, font=font_header, fill=text_header_color)
    
    # ユーザーコード
    text1_x = (new_width - text_width1) // 2
    text1_y = qr_y + qr_height + text_padding
    draw.text((text1_x, text1_y), text1, font=font1, fill=text_color)
    
    # 期限
    text2_x = (new_width - text_width2) // 2
    text2_y = text1_y + text_height1 + 10
    draw.text((text2_x, text2_y), text2, font=font2, fill=text_color)
    
    return gradient

def img2url_present(files):
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
    new_image = edit_present_qrcode(qr_data, usercode, expire_date)
    
    # JSONデータ作成と保存
    json_data = {
        "files": files,
        "response_data": response_data
    }
    json_file_name = os.path.join(save_dir, f"{usercode}.json")
    with open(json_file_name, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    
    # QRコード画像をアップロード
    r = upload_image_to_s3(new_image)
    
    return r

def split_list(input_list, gifts=[], max_size=23):
    """
    リストを指定された上限に従って複数のリストに分割し、
    giftsがどの集合に何個入ったかを返す関数。

    Args:
        input_list (list): 分割する対象のリスト。
        gifts (list): 初めに結合されるリスト。
        max_size (int): 各リストの最大サイズ。

    Returns:
        tuple: 分割されたリストのリストと、giftsの配置状況を示すリスト。
    """
    combined_list = input_list + gifts
    result = []
    gift_counts = []

    for i in range(0, len(combined_list), max_size):
        chunk = combined_list[i:i + max_size]
        result.append(chunk)
        # giftsがこのチャンクに何個入っているかカウント
        gift_counts.append(len([item for item in chunk if item in gifts]))

    return result, gift_counts

def create_gradient_rounded_rect(width, height, radius, start_color, end_color, horizontal=True, scale=4):
    """
    グラデーション付きの丸角長方形画像を作成します。スーパーサンプリングを使用して滑らかなエッジを実現します。

    Args:
        width (int): 幅
        height (int): 高さ
        radius (int): 角の丸み
        start_color (tuple): グラデーションの開始色 (R, G, B)
        end_color (tuple): グラデーションの終了色 (R, G, B)
        horizontal (bool): 水平方向にグラデーションを適用する場合はTrue、垂直方向の場合はFalse
        scale (int): スーパースケーリングの倍率（デフォルトは4）

    Returns:
        Image: 作成された丸角長方形の画像
    """
    # スケーリングされたサイズ
    scaled_width = width * scale
    scaled_height = height * scale
    scaled_radius = radius * scale

    # ベースとなる高解像度の画像を作成（透明）
    base_high_res = Image.new('RGBA', (scaled_width, scaled_height), (255, 255, 255, 0))
    mask_high_res = Image.new('L', (scaled_width, scaled_height), 0)
    draw_mask = ImageDraw.Draw(mask_high_res)
    
    # 丸角長方形のマスクを高解像度で作成
    draw_mask.rounded_rectangle([(0, 0), (scaled_width, scaled_height)], scaled_radius, fill=255)
    
    # グラデーションの作成（高解像度）
    gradient_high_res = Image.new('RGBA', (scaled_width, scaled_height), color=0)
    draw_gradient = ImageDraw.Draw(gradient_high_res)
    
    if horizontal:
        for x in range(scaled_width):
            ratio = x / scaled_width
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            draw_gradient.line([(x, 0), (x, scaled_height)], fill=(r, g, b, 255))
    else:
        for y in range(scaled_height):
            ratio = y / scaled_height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            draw_gradient.line([(0, y), (scaled_width, y)], fill=(r, g, b, 255))
    
    # マスクを適用
    base_high_res.paste(gradient_high_res, (0, 0), mask_high_res)
    
    # 高解像度画像を縮小してアンチエイリアスを適用
    base = base_high_res.resize((width, height), resample=Image.LANCZOS)
    
    return base


def edit_qrcodes(qr_data_list, user_code_list, expire_date, gifts=None):
    assert len(qr_data_list) == len(user_code_list), "QRコードとユーザコードのリストは同じ長さである必要があります。"
    if gifts is None:
        gifts = [None]*len(qr_data_list)
            
    font_path = "./material/NotoSansCJK-Regular.ttc"  # フォントのパス
    font_path2 = "./material/NotoSansCJK-Bold.ttc"  # フォントのパス
    font_size1 = 14  # user_code 用のフォントサイズ
    font_size2 = 17  # expire_date 用のフォントサイズ
    font_size3 = 30  # 枚数表示用のフォントサイズ
    font_size_label = 14  # ラベル内テキスト用のフォントサイズ
    padding = 20  # 画像の余白
    text_padding = -35  # QRコードとテキスト間の余白
    count_padding = -340
    vertical_spacing = 10  # 各QRコード間の間隔
    corner_radius = 20  # 丸角の半径
    background_color = (255, 255, 255, 255)  # 背景色（白）
    text_color = (0, 0, 0, 255)  # テキスト色（黒）
    
    # フォントの読み込み
    font1 = ImageFont.truetype(font_path, font_size1)
    font2 = ImageFont.truetype(font_path, font_size2)
    font3 = ImageFont.truetype(font_path, font_size3)
    font_label = ImageFont.truetype(font_path2, font_size_label)
    
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
    
    # ラベルの設定
    label_start_color = (100, 125, 245)  # #647DF5
    label_end_color = (65, 192, 217)     # #41C0D9
    label_padding_x = 10
    label_padding_y = 5
    
    # QRコードとユーザコードを描画
    for index, (qr, user_code, gift) in enumerate(zip(qr_data_list, user_code_list, gifts), start=1):

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
        count_text_y = current_y + count_padding
        
        draw.text((count_text_x, count_text_y), count_text, font=font3, fill=text_color)

        if isinstance(gift, int) and gift!=0:
            label_text = f"+{gift}枚 特典"
            
        # 「特典x3」ラベルの描画
            label_image = create_gradient_rounded_rect(
                width=75,  # ラベルの幅
                height=22,  # ラベルの高さ
                radius=6,  # 角の丸み
                start_color=label_start_color,
                end_color=label_end_color,
                horizontal=True  # 水平方向のグラデーション
            )
            
            # ラベル内にテキストを描画
            label_draw = ImageDraw.Draw(label_image)
            label_text_width = label_draw.textbbox((0, 0), label_text, font=font_label)[2]
            label_text_height = label_draw.textbbox((0, 0), label_text, font=font_label)[3]
            label_text_x = (label_image.width - label_text_width) // 2
            label_text_y = (label_image.height - label_text_height) // 2 - 2  # 微調整
            label_draw.text((label_text_x, label_text_y), label_text, font=font_label, fill=(255, 255, 255, 255))
            
            # ラベルをメイン画像に貼り付け
            label_x = count_text_x + count_text_width + 15  # 枚数表示の右隣に配置
            label_y = count_text_y + 12  # 微調整
            new_image.paste(label_image, (label_x, label_y), label_image)
        
        current_y += font_size3 + text_padding  # 枚数表示分の高さ調整

    
    # 有効期限を描画
    expire_text = f"プリント期限　 {expire_date}"
    text2_x = (new_width - expire_text_width) // 2
    text2_y = current_y
    draw.text((text2_x, text2_y), expire_text, font=font2, fill=text_color)
    
    return new_image

class HippoError(Exception):
    """Imghippo API エラーを表す例外"""
    pass

def img2url_multi(file_lists, gift_list=[]):
    filess, gift_labels = split_list(file_lists, gift_list)
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
    
        # JSONデータ作成と保存
        json_data = {
            "files": files,
            "response_data": response_data
        }
        json_file_name = os.path.join(save_dir, f"{usercode}.json")
        with open(json_file_name, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    # QRコード編集
    new_image = edit_qrcodes(qr_datas, usercodes, expire_dates[0], gifts=gift_labels)
    # QRコード画像をアップロード
    r = upload_image_to_s3(new_image)
    return r


import boto3
from io import BytesIO
from PIL import Image
import base64
import uuid

class S3UploadError(Exception):
    """S3へのアップロード失敗時に発生する例外"""
    pass

def upload_image_to_s3(image, bucket_name="yat.ss", title=""):
    """
    Amazon S3に画像をアップロードします。

    Args:
        bucket_name (str): S3バケット名。
        image (PIL.Image.Image): アップロードする画像オブジェクト。
        title (str, optional): 画像のタイトル（任意）。

    Returns:
        dict: アップロード結果の情報。
    """
    # S3クライアントを初期化
    s3_client = boto3.client("s3")

    try:
        # 一意のキーを生成
        key = f"{uuid.uuid4()}.png"

        # 画像をBytesIOに保存
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        # タイトルをBase64エンコードしてメタデータに保存
        encoded_title = base64.b64encode(title.encode("utf-8")).decode("ascii") if title else None

        # S3にアップロード
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )
        return f"https://s3.ap-northeast-1.amazonaws.com/yat.ss/{key}"

    except Exception as e:
        raise S3UploadError(f"S3へのアップロードに失敗しました: {e}") from None

# if __name__ == "__main__":
#     # 使用例
#     files = ["./material/size.jpg"] * 2
#     url = img2url(hippo_api_key, files)
#     url


