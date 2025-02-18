from datetime import datetime
from lib.image_meta import get_meta, extract_metadata, get_modelspec
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
    def __init__(self, lambda_cloud_secret, cloudflare_tunnel_token, civitai_token, model_config="./civitdl/models.yml", container_name="sdui"):
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
        self.container_name = container_name

    def __enter__(self):
        self._setup_instance()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._teardown_instance()

    def _setup_instance(self):
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

    def _setup_forge(self, plugins=[]):
        
        cmd = f"""
        git clone https://github.com/sammrai/sd-forge-docker.git
        cd sd-forge-docker &&\
        cp docker-compose-tunnel.yml docker-compose.yml &&\
        echo -e "TUNNEL_TOKEN={self.cloudflare_tunnel_token}\nCIVITAI_TOKEN={self.civitai_token}" > .env
        """
        self.ssh_client.cmd(cmd)

        cmd = f"""
        cd sd-forge-docker &&\
        sudo docker compose up -d
        """
        self.ssh_client.cmd(cmd)

        for plugin in plugins:
            self.install_plugin(plugin)
        self.restart_sdui()

    def restart_sdui(self):
        cmd = f"""
        cd sd-forge-docker
        sudo docker compose exec sdui apt install -y curl
        sudo docker compose exec sdui curl -X POST  http://localhost:7680/sdapi/v1/server-restart
        """
        self.ssh_client.cmd(cmd)

    def _restart_forge_container(self):
        cmd = f"""
        cd sd-forge-docker
        sudo docker compose down
        sudo docker compose up -d
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
        try:
            self.lc.delete_all_resources()
        except:
            print("Failed to delete all resources")
            return

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

    def civitdl(self, model_id, model_type, name=None, download_callback=None):
        if (model_id, model_type) in self.downloaded_models:
            return model_id, model_type
        valid_model_types = ['lora', 'vae', 'embed', 'checkpoint']
        
        # Check if model_type is valid
        if model_type not in valid_model_types:
            raise ValueError(f"Invalid model type: {model_type}. Valid options are: {', '.join(valid_model_types)}.")
        
        # Execute the docker command if model_type is valid
        ret = self.ssh_client.cmd(f"cd sd-forge-docker && sudo docker compose exec {self.container_name} civitdl {model_id} @{model_type}")
        self.downloaded_models.add((model_id, model_type))
        if download_callback:
            download_callback()
        return model_id, model_type

    def install_plugin(self, url):
        self.ssh_client.connect()
        repo_name = url.rstrip('/').split('/')[-1].removesuffix('.git')
        path = f"/app/data/extensions/{repo_name}"
        cmd = f"""
        cd sd-forge-docker
        git clone {url} data/extensions/{repo_name} || true
        sudo docker compose exec -u 0 -w {path} {self.container_name} pip install .
        """
        self.ssh_client.cmd(cmd)


import requests
import json
import os
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
        if response.status_code >= 400:
            raise requests.HTTPError(f"{response.status_code} {response.reason}: {response.text}")

        if response.text == "": return None
        try:
            return response.json()
        except ValueError as e:
            raise RuntimeError(f"レスポンスをJSONとして解析できませんでした。{response.text}")

    def civitdl_get_models(self):
        return self._request("GET", f"civitdl/models/")

    def civitdl_post_models(self, model_id, version_id=None):
        if version_id:
            return self._request("POST", f"civitdl/models/{model_id}/versions/{version_id}")
        else:
            return self._request("POST", f"civitdl/models/{model_id}")

    def civitdl(self, model_id, version_id=None, download_callback=None):
        ret = self.civitdl_post_models(model_id, version_id)
        if download_callback:
            download_callback()
        return ret

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
        # (spec)

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
        # self.post_sdapi_v1_reload_checkpoint()
        self.post_sdapi_v1_refresh_checkpoints()
        self.post_sdapi_v1_refresh_loras()
        # self.post_sdapi_v1_refresh_vae()
        # self.post_sdapi_v1_refresh_embeddings()

        self.models = [
            {"alias": os.path.splitext(os.path.basename(i["filename"]))[0], "path": i["filename"]}
            for i in self.get_sdapi_v1_sd_models()
        ]
        self.model_alias = [i["alias"] for i in self.models]
        # self.samplers = [i["name"] for i in self.get_sdapi_v1_samplers()]
        # self.embeddings = [i["filename"] for i in self.get_sdapi_v1_sd_modules()]
        # self.upscalers = [i["name"] for i in self.get_sdapi_v1_upscalers()]
        self.loras = [{"_alias": i["alias"], "alias": i["name"], "path": i["path"]} for i in self.get_sdapi_v1_loras()]
        self.extensions = self.get_sdapi_v1_extensions()
        print(
            f"models: {len(self.models)},",
            # f"embeddings: {len(self.embeddings)},",
            # f"samplers: {len(self.samplers)},",
            # f"upscalers: {len(self.upscalers)},",
            f"loras: {len(self.loras)},",
            f"extensions: {len(self.extensions)}"
        )

    # fetch_civitai_model_by_name
    def civitai2forge_param(self, filename):
        def get_checkpoint(resource, download=True):
            checkpoint = [i["alias"] for i in self.models if resource["modelName"] in i["path"]]
            if checkpoint:
                return checkpoint[0]
            else:
                if download:
                    spec = get_modelspec(resource["modelName"], type_="checkpoint")
                    print(resource["modelName"])
                    self.civitdl(spec["model_id"], download_callback=self.reload_models)
                    # print("## Downloaded checkpoint: ", resource["modelName"])
                    return get_checkpoint(resource, download=False)
                else:
                    print(f"## Not found checkpoint: \"{resource['modelName']}\"")
                    if self.models:
                        print(f"## Use \"{self.models[0]}\" instead.")
                        return self.models[0]["alias"]
                    else:
                        return None

        def get_lora(resource, download=True):
            lora = [i["alias"] for i in self.loras if resource["modelName"].replace("|","&").replace("/","&") in i["path"]]
            if lora:
                return {lora[0]: resource["weight"]}
            else:
                if download:
                    spec = get_modelspec(resource["modelName"], type_="lora")
                    self.civitdl(spec["model_id"], download_callback=self.reload_models)
                    # print("## Downloaded lora: ", resource["modelName"])
                    return get_lora(resource, download=False)
                else:
                    print("## Not found lora: ", resource["modelName"])
                    return {}
        def get_embed(resource, download=True):
            embed = [i for i in self.embeddings if resource["modelName"] in i and resource["modelVersionName"] in i]
            if embed:
                return [embed[0]]
            else:
                if download:
                    spec = get_modelspec(resource["modelName"], type_="textualinversion")
                    self.civitdl(spec["model_id"], download_callback=self.reload_models)
                    # print("## Downloaded embed: ", resource["modelName"])
                    return get_embed(resource, download=False)
                else:
                    print("## Not found embed: ", resource["modelName"])
                    return []

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

        assert "Civitai resources" in meta["model"], meta
        for resource in meta["model"]['Civitai resources']:
            # print(resource)
            # {'type': 'checkpoint', 'modelVersionId': 1295881, 'modelName': 'WAI-ANI-NSFW-PONYXL', 'modelVersionName': 'v13.0'}
            if resource["type"] == "checkpoint":
                options["sd_model_checkpoint"] = get_checkpoint(resource)
            elif resource["type"] == "lora":
                lora_options.update(get_lora(resource))
            elif resource["type"] == "embed":
                pass
            #     options["forge_additional_modules"] += get_embed(resource)
            else:
                print("## not support type: ", resource["type"], resource["modelName"])
        options["CLIP_stop_at_last_layers"] = meta["model"]['Clip skip']
        return data, options, lora_options, []

    def img2param(self, img_path):
        img_path = get_file_path(img_path)
        metadata = extract_metadata(img_path)
        if "parameters" not in metadata:
            return self.civitai2forge_param(img_path)

        parameters = metadata["parameters"]
        prompt_spec = metadata["prompt_spec"]

        if "options" not in metadata:
            options = {
                "sd_model_checkpoint": metadata["info"]["sd_model_name"],
                "CLIP_stop_at_last_layers": metadata["info"]["clip_skip"],
            }
        else:
            options = metadata["options"]

        options["sd_model_checkpoint"] = self._download_or_get_checkpoint(options.get("sd_model_checkpoint"))
        prompt, loras = self._download_or_get_loras(parameters.get("prompt", ""))
        parameters["prompt"] = prompt
        parameters["seed"] = metadata["info"].get("seed")

        return parameters, options, loras, prompt_spec

    def _download_or_get_checkpoint(self, model_name, download=True):
        model_name = os.path.basename(model_name)  # ファイル名のみ取得
        model_name = os.path.splitext(model_name)[0]  # 拡張子を除去

        if model_name in [i["alias"] for i in self.models]:
            return model_name
        for model in [i["path"] for i in self.models]:
            if model_name in model:
                return model
        
        if download:
            mid, vid = parse_model_string(model_name)
            ret = self.civitdl(mid, vid, download_callback=self.reload_models)
            return self._download_or_get_checkpoint(model_name, download=False)
        else:
            print(f"警告: モデル '{model_name}' が見つかりません。デフォルトモデル '{self.models[0]}' を使用します。")
            return self.models[0]["alias"]
        
    @classmethod
    def extract_loras(cls, prompt):
        lora_pattern = r'<lora:([^:]+):([\d.]+)>'
        lora_matches = re.findall(lora_pattern, prompt)
        loras = {name: float(weight) for name, weight in lora_matches}
        cleaned_prompt = re.sub(lora_pattern, "", prompt).strip(", ")
        return cleaned_prompt, loras

    def _download_or_get_lora(self, model_name, download=True):
        lora_aliases = {lora["alias"] for lora in self.loras}
        if model_name in lora_aliases:
            return model_name
        if download:
            mid, vid = parse_model_string(model_name)
            self.civitdl(mid, vid, download_callback=self.reload_models)
            return self._download_or_get_lora(model_name, download=False)
        else:
            print(f"警告: モデル '{model_name}' が見つかりません。")
            return None
        

    def _download_or_get_loras(self, prompt):
        m = ModelAliasLookup()
        cleaned_prompt, loras = self.extract_loras(prompt)
        parsed = [parse_model_string(lora) for lora in loras]
        
        if all([i is None for i in parsed]):
            loras = {m.get_alias(name): weight for name, weight in loras.items()}
            parsed = [parse_model_string(lora) for lora in loras]

        assert None not in parsed, f"Unexpected None in parsed: {parsed}"
        
        ret_loras = {}
        for lora, weight in loras.items():
            model_name = self._download_or_get_lora(lora)
            if model_name is None: continue
            ret_loras.update({model_name: weight})

        return cleaned_prompt, ret_loras

    def gen(self, *args, **kwargs):
        try:
            return self._gen(*args, **kwargs)
        except KeyboardInterrupt:
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
        assert options["sd_model_checkpoint"], "モデルが指定されていません"
        data = {
            "steps": 20,
            "negative_prompt": "text, lips",
        	"sampler_index":"DPM++ 2M Karras",
        	"width": 832,
        	"height": 1216,
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
        if aspect == "h": data["height"], data["width"] = data["width"], data["height"]

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
            print("change options.")
            model_name = options["sd_model_checkpoint"]
            if model_name not in self.model_alias:
                mid, vid = parse_model_string(model_name)
                self.civitdl(mid, vid)
                forge.reload_models()
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

    def sampling_from_img(self, filename, output_dir="./data/generated/", gen_prompt=False, seed=None, num=1, hr=False, adetailer=False, size=None, remove_words=[], add_prompts=[], enable_masking=None, add_nprompts=[], add_loras={}):

        for _ in range(num):
            if _ != 0 and num!=1 and seed!=-1:
                raise Exception("same seed!")
            data, options, loras, prompt_spec = self.img2param(filename)
            loras.update(add_loras)
            if seed:
                data["seed"] = seed
            if gen_prompt:
                if prompt_spec == [] or prompt_spec == "":
                    print("## prompt_spec is empty. cannnot generate prompt. alternative prompt is used.")
                else:
                    data["prompt"] = generate_prompt(prompt_spec)

            # remove_words に含まれる単語を削除
            for word in remove_words:
                data["prompt"] = data["prompt"].replace(word, "")

            if isinstance(add_prompts, list):
                data["prompt"] += ", " + ", ".join(add_prompts)
            elif hasattr(add_prompts, "__iter__"):
                data["prompt"] += ", " + ", ".join([next(add_prompts)])
            else:
                raise ValueError("add_prompts はリストまたはイテレータである必要があります。")

            # ネガティブプロンプトを結合
            data["negative_prompt"] += ", " + ", ".join(add_nprompts)

            # その他の設定
            if not hr:
                data["enable_hr"] = False
            else:
                data["enable_hr"] = True

            if not adetailer:
                data["alwayson_scripts"] = {}
            if size:
                data["width"], data["height"] = size

            # 生成処理
            ret = self.gen(
                data,
                options,
                loras,
                output_dir=output_dir,
                enable_masking=enable_masking,
                exif={"prompt_spec": prompt_spec, "original_filename": filename},
            )
        return ret


def get_file_path(input_str: str) -> str:
    """
    入力がファイルパスならそのまま返し、URLなら画像をダウンロードして
    /tmp/に保存し、その保存先のパスを返す。

    :param input_str: ファイルパスまたは画像URL
    :return: ファイルのパス
    :raises ValueError: URLのダウンロードに失敗した場合や無効な入力の場合
    """
    # ファイルがローカルに存在する場合
    if os.path.isfile(input_str):
        return input_str

    # URLの場合、ダウンロードして /tmp/ に保存
    try:
        response = requests.get(input_str, stream=True)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生
    except requests.exceptions.RequestException:
        raise ValueError("入力が有効なファイルパスでもURLでもありません。")

    # ファイル名をURLから抽出
    filename = os.path.basename(input_str)
    if not filename:  # URLにファイル名がない場合
        raise ValueError("URLからファイル名を取得できませんでした。")

    # 保存先のパスを作成 (/tmp/ディレクトリ)
    save_path = os.path.join("/tmp", filename)

    # 画像を保存
    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    return save_path


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


import yaml

class ModelAliasLookup:
    def __init__(self, yaml_file="lib/modelspecs.yml", category="lora"):
        self.model_dict = self._load_yaml(yaml_file)
        self.category = category

    def _load_yaml(self, yaml_file):
        """YAML ファイルを読み込んでカテゴリごとの辞書を作成"""
        with open(yaml_file, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
        
        model_dict = {}
        for category, entries in data.items():
            model_dict[category] = {entry["_alias"]: entry["alias"] for entry in entries}
        return model_dict

    def get_alias(self, alias_input):
        """カテゴリと _alias を指定して alias を取得"""
        return self.model_dict.get(self.category, {}).get(alias_input, None)

import re
import os

def parse_model_string(model_string):
    """
    指定されたモデル文字列を解析し、モデル名、モデルID、バージョンIDを抽出する。
    拡張子とディレクトリを除去してから解析を行う。

    Args:
        model_string (str): パスを含む "<モデル名>-mid_<モデルID>-vid_<バージョンID>.拡張子" の形式の文字列

    Returns:
        dict: {"model_name": モデル名, "model_id": モデルID, "version_id": バージョンID} または None（フォーマット不一致時）
    """
    # ディレクトリと拡張子を除去
    # model_string = os.path.basename(model_string)  # ファイル名のみ取得
    # model_string = os.path.splitext(model_string)[0]  # 拡張子を除去

    # パターンマッチング
    pattern = r"^(?P<model_name>.+?)-mid_(?P<model_id>\d+)-vid_(?P<version_id>\d+)$"
    match = re.match(pattern, model_string)
    if match:
        ret = match.groupdict()
        return ret["model_id"], ret["version_id"]
    return None
