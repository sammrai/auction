from PIL import Image
import piexif
import json
import re
import os
import requests
from lib.civitai_query import fetch_civitai_models

# https://wiki.civitai.com/wiki/Civitai_API#GET_/api/v1/models

def extract_metadata(image_path):
    try:
        img = Image.open(image_path)
        exif_data = piexif.load(img.info.get("exif"))
        raw_data = exif_data.get("Exif", {}).get(piexif.ExifIFD.UserComment)
        cleaned_data = raw_data.replace(b'\x00', b'')
        decoded_data = cleaned_data.decode('utf-8', errors='replace')
        json_str = decoded_data.replace('UNICODE', '', 1)
        parsed_data = json.loads(json_str)
        if "extraMetadata" in parsed_data:
            parsed_data["extraMetadata"] = json.loads(parsed_data["extraMetadata"])
        return (parsed_data)
    except (json.decoder.JSONDecodeError, ValueError) as e:
        # JSON解析に失敗した場合の処理
        try:
            # 各行に分割
            json_list = json_str.strip().split("\n")
            
            # "Negative prompt:" の行を見つける
            negative_prompt_index = None
            for i, line in enumerate(json_list):
                if line.startswith("Negative prompt:"):
                    negative_prompt_index = i
                    break
            
            if negative_prompt_index is None:
                raise ValueError("Negative prompt: の行が見つかりません")
            
            # prompt は最初から Negative prompt: の行まで
            prompt_lines = json_list[:negative_prompt_index]
            prompt = "\n".join(prompt_lines).strip()
            
            # nprompt は Negative prompt: の行から最後の行の前まで
            nprompt_lines = json_list[negative_prompt_index:-1]
            nprompt = "\n".join(nprompt_lines).strip()
            # "Negative prompt:   " の部分を削除
            if nprompt.startswith("Negative prompt:"):
                nprompt = nprompt[len("Negative prompt:"):].strip()
            
            # model は最後の行
            model_line = json_list[-1].strip()
            model = parse_raw_text_to_dict(model_line)
            
            parsed_data = {
                "prompt": prompt,
                "negative_prompt": nprompt,
                "model": model
            }
            return parsed_data
        except Exception as inner_e:
            # さらにエラーが発生した場合は詳細なエラーメッセージを出力
            raise ValueError(f"メタデータの解析中にエラーが発生しました: {inner_e}") from e


def parse_raw_text_to_dict(text: str) -> dict:
    # 改行やタブなどをまとめてスペースに置き換え
    text = ' '.join(text.strip().split())

    # 次のトップレベルキーとして見なすのは
    #  (カンマ) + (空白) + (ダブルクォートで始まらない文字列) + (コロン)
    # のパターン、もしくは行末 ($)
    pattern = re.compile(
        r'([^:,]+)\s*:\s*'       # グループ1 -> key
        r'(.*?)'                 # グループ2 -> value (最短じゃなく、次の境界まで)
        r'(?=,\s*[^":]+:|$)',    # 次のキー境界: , から始まり " でない文字 〜 : or 行末
        re.DOTALL
    )

    matches = pattern.findall(text)
    result = {}

    for raw_key, raw_value in matches:
        key = raw_key.strip()
        value_str = raw_value.strip()

        try:
            parsed = json.loads(value_str)
            result[key] = parsed
        except json.JSONDecodeError:
            result[key] = value_str

    return result



def download_image(url, output_dir):
    """画像を指定のディレクトリにダウンロードし、保存パスを返す"""
    filepath = os.path.join(output_dir, os.path.basename(url))
    # print(url,output_dir)
    if os.path.exists(filepath):
        # print(f"File already exists: {filepath}")
        return filepath  # 既存のファイルパスを返す

    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)
    return filepath

def get_meta(file_path):
    output_dir="/tmp"
    try:
        metadata = extract_metadata(file_path)
        # メタデータから image URL を取得
        image_url = metadata.get("26", {}).get("inputs", {}).get("image")
        if not image_url:
            # print(f"No valid image URL in metadata: {file_path}")
            return None, metadata

        downloaded_path = download_image(image_url, output_dir)
        # print(f"Downloaded: {downloaded_path}")
        return metadata, extract_metadata(downloaded_path)
    except KeyError as e:
        print(f"Missing key in metadata for {file_path}: {e}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return None, None



def fetch_civitai_model_by_name(query: str) -> dict:
    """
    Fetches a specific model by name from the CivitAI API based on the query.

    Args:
        query (str): The search query for the API.

    Returns:
        dict: The first matched model details in JSON format if multiple matches exist,
              an empty dictionary if no matches are found.
    """
    model_name = query  # Using query as model_name for exact match
    # Fetch all models using the query
    df = fetch_civitai_models(query)

    # Ensure 'name' column exists in the DataFrame
    if len(df) == 0:
        print(f"# No match found {query}")
        return {}
    # Find the model(s) with the matching name
    matched_models = df[df["name"] == model_name].to_dict(orient="records")
    if len(matched_models) == 0:
        print(f"# No match found {query}")
        return {}
    # Return the first match
    return matched_models[0]



def visualize_lora(data, max_bar_length=10, max_label_length=30):
    """
    辞書の値を基に、テキストベースの滑らかな黒いバーグラフを表示します。

    Args:
        data (dict): キーがラベル、値が数値（0〜1）の辞書。
        max_bar_length (int): バーの最大長。
        max_label_length (int): ラベルの最大表示長。
    """
    for key, value in data.items():
        truncated_key = (key[:max_label_length] + "...") if len(key) > max_label_length else key
        bar_length = int(value * max_bar_length)  # 値をバーの長さにスケール
        bar = "█" * bar_length  # 滑らかな黒いバーを生成
        print(f"{truncated_key:<{max_label_length + 3}} | {bar:<{max_bar_length}} {value:.2f}")

