from datetime import datetime
from lib.image_meta import get_meta, extract_metadata
from lib.lambda_cloud import LambdaCloudController
from lib.ssh_client import SSHClient, convert_to_oneline_echo
from requests.exceptions import HTTPError
import concurrent.futures
import os
import piexif
import time
import re
from lib.nudenet import NudeDetector, save_labeled_image

from IPython.core.interactiveshell import InteractiveShell
InteractiveShell.showtraceback = InteractiveShell.showsyntaxerror


class ForgeResource:
    def __init__(self, lambda_cloud_secret, cloudflare_tunnel_token, civitai_token, model_config="./civitdl/models.yml"):
        self.lambda_cloud_secret = lambda_cloud_secret
        self.cloudflare_tunnel_token = cloudflare_tunnel_token
        self.civitai_token = civitai_token
        self.lc = LambdaCloudController(self.lambda_cloud_secret)
        self.key = None
        self.instance = None
        self.ssh_client = None
        self.model_config = model_config
        self.start_time = None
        self.instance_price_cents_per_hour = None
        self.exchange_rate = 130  # 為替レート (1ドル = 130円)
        self.downloaded_models = set()  # 追加: ダウンロード済みモデルを追跡

    def __enter__(self):
        self._setup_instance()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._teardown_instance()

    def _setup_instance(self, is_forge_install=True):
        self.key, instance = self.lc.launch_instance_wait_auto()
        self.instance = instance[0]
        self.start_time = datetime.now()  # 開始時刻を記録
        self.instance_price_cents_per_hour = self.instance.instance_type.price_cents_per_hour  # 時間あたりの料金（セント単位）を記録

        args = {
            "host": self.instance.ip,
            "username": "ubuntu",
            "key_str": self.key.private_key,
        }
        self.ssh_client = SSHClient(**args)
        self.ssh_client.connect()

        if is_forge_install: 
            print("setting up forge")
            self._setup_environment()

    def _setup_environment(self):
        
        cmd = f"""
        git clone https://github.com/sammrai/sd-forge-docker.git
        cd sd-forge-docker
        cp docker-compose-tunnel.yml docker-compose.yml
        echo -e "TUNNEL_TOKEN={self.cloudflare_tunnel_token}\nCIVITAI_TOKEN={self.civitai_token}" > .env
        sudo docker compose up -d
        """
        self.ssh_client.cmd(cmd)

    def _download_models(self, model_config):
        cmd = f"""
        cd sd-forge-docker
        {convert_to_oneline_echo(model_config, "models.yml")}
        bash -lc './fetch_models.sh models.yml ./data/webui 3'
        """
        self.ssh_client.cmd(cmd)


    def _teardown_instance(self):
        if self.ssh_client:
            self.ssh_client.disconnect()

        if self.lc:
            self.lc.terminate_instances([self.instance.id])
            self.lc.delete_ssh_key(self.key.id)

        if self.start_time and self.instance_price_cents_per_hour:
            elapsed_time = datetime.now() - self.start_time
            elapsed_minutes = elapsed_time.total_seconds() / 60  # 分単位に変換
            cost_cents = (elapsed_minutes / 60) * self.instance_price_cents_per_hour  # セント単位で計算
            cost_dollars = cost_cents / 100
            cost_yen = cost_dollars * self.exchange_rate  # 円換算

            print(f"Instance was used for {elapsed_minutes:.2f} minutes. Total cost: ¥{cost_yen:.2f}")

    def get_current_cost(self):
        """
        現在のコストを計算して日本円で返す。
        """
        if not self.start_time or not self.instance_price_cents_per_hour:
            return 0  # インスタンスがセットアップされていない場合

        elapsed_time = datetime.now() - self.start_time
        elapsed_minutes = elapsed_time.total_seconds() / 60
        cost_cents = (elapsed_minutes / 60) * self.instance_price_cents_per_hour
        cost_dollars = cost_cents / 100
        cost_yen = cost_dollars * self.exchange_rate
        return round(cost_yen, 2)  # 小数点第2位で丸める

    def _all_delete(self):
        self.lc.delete_all_resources()

    def civitdl_parallel(self, models, max_workers=3, force=False):
        self.ssh_client.connect()
        if force:
            self.downloaded_models.clear()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.civitdl, model['model_id'], model['model_type'], model.get('name'))
                for model in models
            ]
            try:
                for future in tqdm(
                    concurrent.futures.as_completed(futures),
                    total=len(futures),
                    desc="Downloading models"
                ):
                    try:
                        future.result()
                    except Exception as exc:
                        print(f"Model download failed: {exc}")

            except KeyboardInterrupt:
                print("KeyboardInterrupt detected. Cancelling all threads...")
                # ここで全ての未完了タスクをキャンセル
                for f in futures:
                    f.cancel()
                # raise しないと以降のコードを止められないので再度送出
                raise

    def civitdl(self, model_id, model_type, name=None):
        if (model_id, model_type) in self.downloaded_models:
            return model_id, model_type
        valid_model_types = ['lora', 'vae', 'embed', 'checkpoint']
        
        # Check if model_type is valid
        if model_type not in valid_model_types:
            raise ValueError(f"Invalid model type: {model_type}. Valid options are: {', '.join(valid_model_types)}.")
        
        # Execute the docker command if model_type is valid
        ret = self.ssh_client.cmd(f"cd sd-forge-docker && sudo docker compose exec webui civitdl {model_id} @{model_type}")
        self.downloaded_models.add((model_id, model_type))
        return model_id, model_type

    def install_plugin(self, url):
        self.ssh_client.connect()
        repo_name = url.rstrip('/').split('/')[-1].removesuffix('.git')
        path = f"/app/data/extensions/{repo_name}"
        cmd = f"""
        cd sd-forge-docker
        git clone {url} data/extensions/{repo_name} || true
        sudo docker compose exec -u 0 -w {path} webui pip install .
        """
        self.ssh_client.cmd(cmd)


import requests
import json
import os
from openapi_spec_validator import validate_spec
import inflection


class ForgeAPI:
    def __init__(self, base_url, client_id, client_secret, openapi_path="lib/openapi.json"):
        """
        Forge APIクラスの初期化
        :param base_url: Forge APIのベースURL
        :param client_id: Cloudflare Access Client ID
        :param client_secret: Cloudflare Access Client Secret
        :param openapi_path: OpenAPI仕様ファイルのパス（オプション）
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "CF-Access-Client-Id": client_id,
            "CF-Access-Client-Secret": client_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.models = [None]
        self.samplers = [None]
        self.embeddings = [None]
        self.upscalers = [None]
        self.loras = [None]
        self.extensions = [None]
        if openapi_path:
            self.load_openapi(openapi_path)
        self.wait_until_startup()
        self.nude_detector = NudeDetector("models/640m.onnx")
        self.reload_models()

    def _request(self, method, endpoint, **kwargs):
        """
        内部HTTPリクエストメソッド
        :param method: HTTPメソッド（GET, POSTなど）
        :param endpoint: エンドポイント
        :param kwargs: その他のリクエストオプション（params, json, dataなど）
        :return: JSON形式のレスポンスデータ
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()  # HTTPステータスエラーをスロー
        try:
            return response.json()
        except ValueError:
            raise RuntimeError("レスポンスをJSONとして解析できませんでした。")


    def load_openapi(self, openapi_path):
        """
        OpenAPI仕様を読み込み、動的にメソッドを追加する
        :param openapi_path: OpenAPI仕様ファイルのパス
        """
        if not os.path.exists(openapi_path):
            raise FileNotFoundError(f"OpenAPIファイルが見つかりません: {openapi_path}")

        with open(openapi_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)

        # OpenAPI仕様のバリデーション
        # validate_spec(spec)

        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for http_method, operation in methods.items():
                method_name = self._generate_method_name(operation, path, http_method)
                self._add_method(method_name, http_method.upper(), path, operation)

    def _generate_method_name(self, operation, path, http_method):
        """
        メソッド名を生成する
        :param operation: OpenAPIのoperationオブジェクト
        :param path: APIパス
        :param http_method: HTTPメソッド
        :return: メソッド名（snake_case）
        """
        # if "operationId" in operation:
        #     method_name = inflection.underscore(operation["operationId"])
        # else:
        # パスとHTTPメソッドからメソッド名を生成
        clean_path = path.strip('/').replace('/', '_').replace('{', '').replace('}', '')
        method_name = f"{http_method}_{clean_path}"
        # print(method_name, http_method, clean_path, path)
        method_name = inflection.underscore(method_name)
        return method_name

    def _add_method(self, method_name, http_method, path, operation):
        """
        動的にメソッドをクラスに追加する
        :param method_name: 追加するメソッドの名前
        :param http_method: HTTPメソッド
        :param path: APIパス
        :param operation: OpenAPIのoperationオブジェクト
        """

        def api_method(*args, **kwargs):
            # パスパラメータの置換
            url = path
            path_params = {}
            if "parameters" in operation:
                for param in operation["parameters"]:
                    if param["in"] == "path":
                        param_name = param["name"]
                        if param_name in kwargs:
                            path_params[param_name] = kwargs.pop(param_name)
                        else:
                            raise ValueError(f"Missing path parameter: {param_name}")
            for key, value in path_params.items():
                url = url.replace(f"{{{key}}}", str(value))

            # クエリパラメータ
            params = {}
            if "parameters" in operation:
                for param in operation["parameters"]:
                    if param["in"] == "query":
                        param_name = param["name"]
                        if param_name in kwargs:
                            params[param_name] = kwargs.pop(param_name)

            # リクエストボディ
            json_body = None
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                if "application/json" in content:
                    json_body = kwargs.get("json")
                    if json_body is None:
                        raise ValueError("Missing JSON body for the request.")

            return self._request(http_method, url, params=params, json=json_body)

        # メソッドにドキュメント文字列を追加
        api_method.__doc__ = operation.get("description", f"{http_method} {path}")
        # メソッドをクラスに追加
        setattr(self, method_name, api_method)

    def wait_until_startup(self, max_retries=60, delay=1):
        for _ in range(max_retries):
            try:
                self.get_sdapi_v1_options()
                return 
            except HTTPError:
                time.sleep(delay)
        raise RuntimeError("Maximum retries reached for forge.get_sdapi_v1_options()")

    def restart(self):
        try:
            self.post_sdapi_v1_server_restart()
        except HTTPError as e:
            pass
        self.wait_until_startup()

    def reload_models(self):
        self.post_sdapi_v1_reload_checkpoint()
        self.post_sdapi_v1_refresh_checkpoints()
        self.post_sdapi_v1_refresh_loras()
        self.post_sdapi_v1_refresh_vae()
        self.post_sdapi_v1_refresh_embeddings()
        self.models = [i["title"].replace(".tmp/","") for i in self.get_sdapi_v1_sd_models()]
        self.samplers = [i["name"] for i in self.get_sdapi_v1_samplers()]
        self.embeddings = [i["filename"] for i in self.get_sdapi_v1_sd_modules()]
        self.upscalers = [i["name"] for i in self.get_sdapi_v1_upscalers()]
        self.loras = [{"alias": i["alias"], "path": i["path"]} for i in self.get_sdapi_v1_loras()]
        self.extensions = self.get_sdapi_v1_extensions()
        print(f"models: {len(self.models)}",
                f"embeddings: {len(self.embeddings)}",
                f"samplers: {len(self.samplers)}",
                f"embeddings: {len(self.embeddings)}",
                f"upscalers: {len(self.upscalers)}",
                f"loras: {len(self.loras)}",
                f"extensions: {len(self.extensions)}"
             )

    # fetch_civitai_model_by_name
    def civitai2forge_param(self, filename):
        models, embeddings, loras = self.models, self.embeddings, self.loras
        meta = get_meta(filename)[1]
        
        data = {
            "prompt": meta["prompt"],
            "negative_prompt": meta["negative_prompt"],
            "steps": meta["model"]["Steps"],
            "sampler_index": meta["model"]["Sampler"],
            "width": meta["model"]["Size"].split("x")[0],
            "height": meta["model"]["Size"].split("x")[1],
            "cfg_scale": meta["model"]["CFG scale"],
            "seed": meta["model"]["Seed"],    
        }
        options = {
            "forge_additional_modules" : []
        }
        lora_options = {}
        
        for resource in meta["model"]['Civitai resources']:
            # print(resource)
            if resource["type"] == "checkpoint":
                checkpoint = [i for i in models if resource["modelName"] in i]
                if checkpoint:
                    checkpoint = checkpoint[0]
                else:
                    self.models[0]
                if checkpoint:
                    options["sd_model_checkpoint"] = checkpoint
                else:
                    print("## not found checkpoint: ", resource["modelName"])
            elif resource["type"] == "lora":
                lora = [i["alias"] for i in loras if resource["modelName"].replace("|","&").replace("/","&") in i["path"]]
                if lora:
                    lora_options[lora[0]] = resource["weight"]
                    # options["forge_additional_modules"].append(lora[0])
                else:
                    print("## not found lora: ", resource["modelName"])
            elif resource["type"] == "embed":
                embed = [i for i in embeddings if resource["modelName"] in i and resource["modelVersionName"] in i]
                if embed:
                    options["forge_additional_modules"].append(embed[0])
                else:
                    print("## not found embed: ", resource["modelName"])
                    
            else:
                print("## not support type: ", resource["type"], resource["modelName"])
        options["CLIP_stop_at_last_layers"] = meta["model"]['Clip skip']
        
        return data, options, lora_options, []

    def img2param(self, img_path):
        metadata = extract_metadata(img_path)
        
        if "parameters" not in metadata:
            # Civitai画像の場合
            return self.civitai2forge_param(img_path)
        
        parameters = metadata["parameters"]
        prompt_spec = metadata.get("prompt_spec", "")
        options = metadata.get("options", {
            "sd_model_checkpoint": self.models[0] if self.models else None,
            "CLIP_stop_at_last_layers": 2,
        })

        # `sd_model_checkpoint` の正しい参照を確認
        options["sd_model_checkpoint"] = self._resolve_model_checkpoint(options.get("sd_model_checkpoint", ""))
        
        # LoRA パラメータの抽出と検証
        prompt, loras = self._extract_and_validate_loras(parameters.get("prompt", ""))
        
        parameters["prompt"] = prompt
        parameters["seed"] = metadata["info"].get("seed")
        
        return parameters, options, loras, prompt_spec

    def _resolve_model_checkpoint(self, checkpoint):
        if checkpoint in self.models:
            return checkpoint
        
        # ハッシュを除去して一致をチェック
        base_name = re.sub(r" \[.*\]$", "", checkpoint)
        
        matched_model = next((model for model in self.models if model.startswith(base_name)), None)
        
        if not matched_model:
            print(f"警告: モデル '{checkpoint}' が見つかりません。デフォルトモデル '{self.models[0]}' を使用します。")
            return self.models[0]
        
        return matched_model

    @classmethod
    def extract_loras(cls, prompt):
        lora_pattern = r'<lora:([^:]+):([\d.]+)>'
        lora_matches = re.findall(lora_pattern, prompt)
        loras = {name: float(weight) for name, weight in lora_matches}
        cleaned_prompt = re.sub(lora_pattern, "", prompt).strip(", ")
        return cleaned_prompt, loras

    def _extract_and_validate_loras(self, prompt):
        cleaned_prompt, loras = self.extract_loras(prompt)
        lora_aliases = {lora["alias"] for lora in self.loras}
        missing_loras = [name for name in loras if name not in lora_aliases]
        
        if missing_loras:
            raise ValueError(f"Missing LoRA aliases: {missing_loras}")
        
        return cleaned_prompt, loras

    def gen(self, *args, **kwargs):
        try:
            return self._gen(*args, **kwargs)
        except KeyboardInterrupt:
            print("処理を中止します")
            self.post_sdapi_v1_interrupt()
            # 元の例外との関連付けを削除
            raise UserWarning("処理を中止しました") from None

    def _gen(self, _data, options,
            lora_options={},
            dpi=200,
            output_dir="./data/generated",
            delete_dir="./data/generated/dev",
            exif={},
            show=False,
            hr=None,
            aspect="v",
            adetailer="person",
            enable_masking=None,
        ):
        """
        入力データに基づいて画像を生成し、表示および保存します。
        data: 画像生成用のデータ（バッチサイズに応じて複数の画像を生成）
        """
        assert aspect in ["v", "h"]
        data = {
            "steps": 20,
            "negative_prompt": "text, lips",
        	# "sampler_index":"Euler A",
        	"sampler_index":"DPM++ 2M Karras",
        	"width": 832,
        	"height": 1216,
        	# "width": 256,
        	# "height": 384,
        	"cfg_scale": 7,
        	"seed": -1,
            "batch_size": 1,

            # upscale
            "enable_hr":hr,
        	"hr_scale": 2,
        	"hr_upscaler": "Lanczos",
            "denoising_strength":0.5,
            "hr_additional_modules": [],
        }
        if aspect == "h":
            data["height"], data["width"] = data["width"], data["height"]

        if adetailer == "person":
            data["alwayson_scripts"] = adetailer_person
        elif adetailer == "face":
            data["alwayson_scripts"] = adetailer_face
        else:
            data["alwayson_scripts"] = {}

        # APIへのオプション送信
        # optionが違う時に送信する
        current_optons = self.get_sdapi_v1_options()
        if not all(current_optons[k] == options[k] for k in current_optons.keys() & options.keys()):
            self.post_sdapi_v1_options(json=options)

        # プロンプトにLoRAオプションを追加
        data.update(_data)
        if hr is not None:
            data["enable_hr"] = hr

        # LoRAオプションの文字列化
        lora_str = ", " + ", ".join([f"<lora:{k}:{v}>" for k, v in lora_options.items()])
        data["prompt"] += lora_str
        
        # 生成画像の保存先ディレクトリを作成
        os.makedirs(output_dir, exist_ok=True)
        
        # 画像生成APIの呼び出し
        response = self.post_sdapi_v1_txt2img(json=data)
        images = response.pop("images")
        response["info"] = json.loads(response["info"])
        response["options"] = options
        response.update(exif)
    
        # 現在の日時を基にしたファイル名フォーマット
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
        # 各画像を保存
        for i, img in enumerate(images):            
            # 画像データをデコード
            img_data = base64.b64decode(img)
            image = Image.open(io.BytesIO(img_data))
            
            # JPEGはRGBモードを必要とするため、変換が必要な場合は変換
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            # JSONメタデータを文字列に変換
            json_metadata = json.dumps(response, ensure_ascii=False)
            
            # EXIFのUserCommentフィールドにメタデータを埋め込む
            # UserCommentのエンコード（Unicode）
            user_comment_prefix = b"UNICODE\0"  # Unicodeを示すプレフィックス
            user_comment_encoded = user_comment_prefix + json_metadata.encode('utf-8')  # UTF-16エンコードを使用
            
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment_encoded
            
            # EXIFバイトデータを生成
            exif_bytes = piexif.dump(exif_dict)
            
            # クラスと位置のリストを返す
            predictions = self.nude_detector.detect_specific_classes(image)
            
            # もしマスキング有効無効と、推定結果の有無に齟齬がある場合は、ngをつける。そうでないときは何もつけない
            # 成人向け画像に、健全画像が混ざることを防ぎ、逆に健全画像にはマスキングがかかっていないことを保証する
            if enable_masking is not None and enable_masking != (len(predictions) >= 1):
                prefix = "ng_"
                output_dir = delete_dir
            else:
                prefix = ""

            file_path = os.path.join(output_dir,f"{prefix}{timestamp}_{i}.jpg")
            base, ext = os.path.splitext(file_path)
            labeled_file_path = f"{base}_label.png"

            # 画像をJPEG形式で保存し、EXIFデータを埋め込む
            image.save(file_path, "JPEG", exif=exif_bytes, quality=95)
            save_labeled_image(file_path, labeled_file_path, predictions)

        # 画像を横に並べて表示
        if show:
            show_images(images, dpi=dpi)
        
        return response
    
    import random

    def sampling_from_img(self, filename, output_dir="./data/generated/", gen_prompt=False, seed=None, num=1, hr=False, adetailer=False, size=None, remove_words=[], add_prompts=[], enable_masking=None, add_nprompts=[]):
        for _ in range(num):
            data, options, loras,prompt_spec = self.img2param(filename)
            if seed:
                data["seed"]=seed
            if gen_prompt:
                data["prompt"] = generate_prompt(prompt_spec)

            for word in remove_words:
                data["prompt"] = data["prompt"].replace(word,"")
            data["prompt"] += ","+ " ".join(add_prompts)
            data["negative_prompt"] += ","+ " ".join(add_nprompts)
            print(data["prompt"])

            if not hr:
                data["enable_hr"] = False
            if not adetailer:
                data["alwayson_scripts"] = {}
            if size:
                data["width"], data["height"] = size

            ret = self.gen(data,
                    options, 
                    loras,
                    output_dir = output_dir,
                    enable_masking = enable_masking,
                    exif={"prompt_spec": prompt_spec}
            )
        return ret
            

import time
import signal
from tqdm import tqdm  # tqdmをインポート

class TaskRunner:
    def __init__(self, task_func, total=100, args=(), kwargs=None):
        """
        TaskRunnerの初期化

        :param task_func: 実行するタスク関数
        :param total: タスクを実行する総回数
        :param args: タスク関数に渡す位置引数のタプル
        :param kwargs: タスク関数に渡すキーワード引数の辞書
        """
        self.task_func = task_func
        self.total = total
        self.terminate = False
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        # シグナルハンドラを登録
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        """
        シグナルハンドラ。終了フラグを設定し、ユーザーに通知します。
        """
        self.terminate = True
        print("\n終了信号を受け取りました。現在のタスクが完了した後に終了します。")

    def run(self):
        """
        タスクを指定回数実行します。終了信号が受け取られた場合、現在のタスク完了後にループを終了します。
        進捗バーを表示します。
        """
        with tqdm(total=self.total, desc="タスクの進捗", unit="タスク") as pbar:
            for i in range(1, self.total + 1):
                if self.terminate:
                    print(f"ループを {i-1} 回目で終了します。")
                    break
                # try:
                self.task_func(*self.args, **self.kwargs)
                # except Exception as e:
                    # print(f"タスク実行中にエラーが発生しました: {e}")
                pbar.update(1)  # プログレスバーを更新
        print("ループが安全に終了しました。")

import os
import json
import base64
from datetime import datetime
from PIL import Image, PngImagePlugin
import io
import threading
from tqdm import tqdm
import time
import matplotlib.pyplot as plt



# def gen_progress(data):
#     """
#     入力データに基づいて画像を生成し、表示および保存します。
#     data: 画像生成用のデータ（バッチサイズに応じて複数の画像を生成）
#     """
#     os.makedirs("./generated", exist_ok=True)  # 保存先ディレクトリを作成

#     # プログレス監視用のフラグ
#     progress_done = threading.Event()

#     # プログレス監視関数
#     def monitor_progress():
#         try:
#             # 最初に総ジョブ数を取得
#             initial_progress_data = forge.get_sdapi_v1_progress()
#             total_jobs = initial_progress_data.get("state", {}).get("job_count", 1)
#             current_job_no = initial_progress_data.get("state", {}).get("job_no", 0)

#             # 1ベースに変換
#             display_job_no = current_job_no + 1

#             with tqdm(total=100, desc=f"Job {display_job_no}/{total_jobs}", unit="%", leave=True) as pbar:
#                 while not progress_done.is_set():
#                     progress_data = forge.get_sdapi_v1_progress()
#                     progress_data.pop("current_image")
#                     print(progress_data)

#                     state = progress_data.get("state", {})
#                     job_count = state.get("job_count", 1)
#                     job_no = state.get("job_no", 0)
#                     progress = progress_data.get("progress", 0) * 100  # パーセンテージに変換

#                     # デバッグ用: print(job_count, job_no)

#                     # ジョブ番号の1ベース表示
#                     new_display_job_no = job_no + 1

#                     # ジョブが進行中のジョブ番号を取得
#                     if job_no != current_job_no:
#                         # 新しいジョブに切り替わった場合
#                         pbar.set_description(f"Job {new_display_job_no}/{total_jobs}")
#                         current_job_no = job_no

#                     # 進捗を更新
#                     pbar.n = int(progress)
#                     pbar.refresh()

#                     # 生成が完了したか確認
#                     if progress_data.get("is_complete", False):
#                         break

#                     time.sleep(1)  # 進捗確認の間隔

#                 # 最終的に進捗を100%に設定して終了
#                 pbar.n = 100
#                 pbar.refresh()
#         except Exception as e:
#             print(f"進捗監視中にエラーが発生しました: {e}")

#     # プログレス監視スレッドを開始
#     monitor_thread = threading.Thread(target=monitor_progress)
#     monitor_thread.start()

#     # 画像生成APIを同期的に呼び出し
#     response = forge.post_sdapi_v1_txt2img(json=data)

#     # 進捗監視を終了
#     progress_done.set()
#     monitor_thread.join()

#     # 生成された画像データを取得
#     images = response.pop("images")

#     # 現在の日時を基にしたファイル名フォーマット
#     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

#     # 各画像を保存
#     for i, img in enumerate(images):
#         file_path = f"./generated/{timestamp}_{i}.png"
#         meta_path = f"./generated/{timestamp}_{i}.json"

#         # JSON形式のレスポンスを保存
#         with open(meta_path, "w", encoding="utf-8") as json_file:
#             json.dump(response, json_file, ensure_ascii=False, indent=4)

#         # メタデータを埋め込みつつ画像を保存
#         img_data = base64.b64decode(img)
#         image = Image.open(io.BytesIO(img_data))

#         # メタデータ埋め込み用
#         metadata = PngImagePlugin.PngInfo()
#         metadata.add_text("description", json.dumps(response, ensure_ascii=False))

#         image.save(file_path, "PNG", pnginfo=metadata)

#     # 画像を横に並べて表示
#     show_images(images)


def show_images(images, dpi=50):
    """
    画像を横に並べて隙間なく表示します（大きな表示に対応）。
    """
    decoded_images = [Image.open(io.BytesIO(base64.b64decode(img))) for img in images]
    
    # DPIを設定して大きく表示
    fig, axes = plt.subplots(1, len(decoded_images), figsize=(len(decoded_images) * 6, 6), dpi=dpi)
    fig.subplots_adjust(wspace=0)  # 隙間をなくす
    
    if len(decoded_images) == 1:
        axes = [axes]  # 画像が1枚の場合に対応
    
    for ax, img in zip(axes, decoded_images):
        ax.imshow(img)
        ax.axis("off")
    plt.show()

import random


def random_step(start=0.0, stop=1.0, step=0.1):
    # 指定したステップで範囲内の値を生成し、その中からランダムに選択
    steps = [round(start + i * step, 10) for i in range(int((stop - start) / step) + 1)]
    return random.choice(steps)

def generate_prompt(design):
    """
    デザインリストを基にプロンプトを生成。
    リストの場合はランダムに1つ選択、固定値はそのまま使用。
    """
    prompt_parts = []
    for item in design:
        if isinstance(item, list):
            prompt_parts.append(random.choice(item))
        else:
            prompt_parts.append(item)
    return (", ".join(prompt_parts)).replace(", @", " ")


adetailer_face={"ADetailer": {"args": [{"ad_model": "face_yolov8n.pt",}]}}
adetailer_person={"ADetailer": {"args": [{"ad_model": "person_yolov8s-seg.pt",}]}}

# 使用例
if __name__ == "__main__":
    lambda_cloud_secret = "secret_mac-m1_f8dbcd564f2c4500896dc7f31ac2141a.Sq0eBUd5PhHqCSax0447lHJR8ujylk8j"
    cloudflare_tunnel_token = "eyJhIjoiZWU1YzJhMThmYmQ1OTA5OTQyMDI3NmMzNzA5ZjkyYTYiLCJ0IjoiZWYzNWM3YzYtMjIwNS00MDYwLWEzNzQtNTE3YWVmMzZhYWI5IiwicyI6Ill6azFaak5rTVdVdFpUVm1ZaTAwWmpaakxUa3haamd0TVRBMU5tUTVPVGs0T0dZNCJ9"
    civitai_token = "d55180e3db1da5b67a75e98cec927fe0"

    with ForgeResource(lambda_cloud_secret, cloudflare_tunnel_token, civitai_token) as forge:
        print("Forge instance is set up and ready.")

    print("Forge instance is cleaned up.")
