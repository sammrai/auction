from PIL import Image as PILImage, ImageDraw, ImageFilter, ImageFont, Image

import numpy as np
import os
import matplotlib.pyplot as plt


class LabelImageNotFoundError(Exception):
    pass


class AspectRatioMismatchError(Exception):
    pass


class ResolutionError(Exception):
    pass


class MyImage:
    def __init__(self, image_path, label_color=(0, 255, 0, 255), tolerance=2, aspect_ratio_tolerance=1e-1, padding=0):
        self.image_path = image_path
        self.original_image = PILImage.open(image_path).convert("RGBA")
        self.image = self.original_image.copy()
        self.label_color = label_color
        self.tolerance = tolerance
        self.aspect_ratio_tolerance = aspect_ratio_tolerance
        self.label_image = self._load_label_image()
        self.label_mask = None
        self.saved_file_path = None

        # 解像度チェック
        self._check_resolution()

        if not self.label_image:
            raise LabelImageNotFoundError(f"Label image not found for {image_path}")

        self._check_aspect_ratio()
        self._generate_label_mask(padding=padding)
        self.filters_applied = []

    def _check_resolution(self):
        """
        画像の解像度が基準を下回らないことを確認する
        """
        min_width, min_height = 1536, 2304  # 縦横を考慮した最低解像度
        width, height = self.image.size

        if not ((width >= min_width and height >= min_height) or (width >= min_height and height >= min_width)):
            raise ResolutionError(
                f"Image resolution too low: {width}x{height}. Minimum required: {min_width}x{min_height} or {min_height}x{min_width}¥n{self.image_path}"
            )
    def _load_label_image(self):
        label_path = self.image_path.replace(".jpg", "_label.png")
        try:
            label_image = PILImage.open(label_path).convert("RGBA")
            # print(f"Loaded label image: {label_path}")
            return label_image
        except FileNotFoundError:
            return None
        except Exception as e:
            raise Exception(f"{e,self.image_path}")
            

    def _check_aspect_ratio(self):
        label_aspect = self.label_image.width / self.label_image.height
        image_aspect = self.image.width / self.image.height
        if abs(label_aspect - image_aspect) > self.aspect_ratio_tolerance:
            raise AspectRatioMismatchError(
                f"Aspect ratio mismatch: label({label_aspect:.6f}) vs image({image_aspect:.6f})"
            )

    def _generate_label_mask(self, padding=0):
        """効率的にラベルマスクを生成し、指定されたパディング量で領域を拡張"""
        label_resized = self.label_image.resize(self.image.size)
        label_array = np.array(label_resized)
    
        target_color = np.array(self.label_color[:3])
        diff = np.abs(label_array[..., :3] - target_color)
    
        mask = np.all(diff <= self.tolerance, axis=-1).astype(np.uint8) * 255
    
        # ラベル領域が存在しない場合のチェック
        # if np.sum(mask) == 0:
            # raise ValueError(f"ラベル画像に指定された色 {self.label_color} が存在しません: {self.image_path}")
    
        self.label_mask = PILImage.fromarray(mask, mode="L")
    
        # パディング処理
        if padding > 0:
            self.label_mask = self._expand_mask(self.label_mask, padding)

    def _expand_mask(self, mask, padding):
        """
        マスク領域を指定されたパディング量で拡張します。
        
        Args:
            mask (PIL.Image): ラベルのマスク画像。
            padding (int): 拡張するピクセル数。
        
        Returns:
            PIL.Image: 拡張されたマスク画像。
        """
        # マスク画像を NumPy 配列に変換
        mask_array = np.array(mask)
        
        # NumPy 配列で膨張処理を実行
        structure = np.ones((2 * padding + 1, 2 * padding + 1), dtype=np.uint8)
        expanded_array = np.where(
            mask_array > 0, 1, 0
        )  # バイナリ化
        expanded_array = np.pad(expanded_array, padding, mode="constant", constant_values=0)
        expanded_array = np.clip(
            np.convolve(expanded_array.flatten(), structure.flatten(), "same").reshape(expanded_array.shape), 
            0, 1,
        ).astype(np.uint8)

        # 元のマスクサイズに戻す
        expanded_array = expanded_array[
            padding:-padding or None, padding:-padding or None
        ]
        # PIL Image に戻して返す
        return PILImage.fromarray((expanded_array * 255).astype(np.uint8), mode="L")

    def _copy_with_current_state(self):
        """現在の状態をコピーした新しいインスタンスを生成"""
        new_instance = self.__class__.__new__(self.__class__)  # __init__ を呼び出さず新しいインスタンスを生成
        new_instance.image_path = self.image_path
        new_instance.original_image = self.original_image
        new_instance.image = self.image.copy()
        new_instance.label_color = self.label_color
        new_instance.tolerance = self.tolerance
        new_instance.aspect_ratio_tolerance = self.aspect_ratio_tolerance
        new_instance.label_image = self.label_image
        new_instance.label_mask = self.label_mask.copy() if self.label_mask else None
        new_instance.filters_applied = self.filters_applied.copy()
        new_instance.saved_file_path = self.saved_file_path
        return new_instance


    def apply_filter(self, filter_instance):
        """フィルタを適用"""
        new_image = self._copy_with_current_state()
        filter_instance.apply(new_image)
        new_image.filters_applied.append(filter_instance.__class__.__name__)
        return new_image
    
    def save(self, suffix=None, skip_if_exists=False, quality=95):
        """
        画像を保存します。サフィックスを指定することで、ファイル名に特定の文字列を追加できます。
    
        Args:
            suffix (str or None): ファイル名に追加するサフィックス。指定しない場合は適用されたフィルタ名を使用。
            skip_if_exists (bool): True の場合、ファイルが既に存在していればスキップします。
            quality (int): JPEG保存時の品質（1-100）。デフォルトは95。
    
        Returns:
            self: メソッドチェーンを可能にするために self を返します。
        """
        # ファイル名と拡張子を分離
        assert suffix != "", "Suffix cannot be an empty string."
        assert suffix != "label", "Suffix 'label' is not allowed."
        base_name, ext = os.path.splitext(self.image_path)
    
        if suffix:
            # 指定されたサフィックスがある場合
            output_suffix = f"_{suffix}"
        elif self.filters_applied:
            # サフィックスが指定されておらず、フィルタが適用されている場合
            filters_suffix = "_".join(self.filters_applied)
            output_suffix = f"_{filters_suffix}"
        else:
            raise Exception("Suffix must be specified or filters must be applied.")
    
        # 新しいファイル名を生成
        output_path = f"{base_name}{output_suffix}{ext}"
        self.saved_file_path = output_path
    
        if skip_if_exists and os.path.exists(output_path):
            # print(f"File already exists. Skipping: {output_path}")
            pass
        else:
            # JPEGの場合、品質を指定して保存
            save_kwargs = {"optimize": True}
            if ext.lower() in ['.jpg', '.jpeg']:
                save_kwargs['quality'] = quality
    
            # 画像を保存
            self.image.convert("RGB").save(output_path, **save_kwargs)
            # print(f"Image saved to {output_path}")
    
        return self
        
    def show_image(self, scale=1.0, show_mask=False):
        """
        Jupyter Notebook上で画像を表示します。
        
        Args:
            scale (float): 表示する画像のスケール（倍率）。デフォルトは1.0。
            show_mask (bool): Trueの場合、ラベルマスクを表示します。
        """
        if show_mask:
            if self.label_mask is not None:
                image_array = np.array(self.label_mask)
            else:
                raise ValueError("Label mask is not generated.")
        else:
            image_array = np.array(self.image)
    
        # スケールを適用
        scaled_width = int(image_array.shape[1] * scale)
        scaled_height = int(image_array.shape[0] * scale)
    
        # 画像サイズをスケール調整
        scaled_image = PILImage.fromarray(image_array).resize((scaled_width, scaled_height))
    
        # Matplotlibで表示
        plt.figure(figsize=(8, 8))
        plt.imshow(scaled_image)
        plt.axis('off')  # 軸を非表示
        plt.show()
        
    @staticmethod
    def _get_related_files(image_path, skip_suffix=None):
        """
        元画像の派生ファイルをチェックし、指定されたサフィックスが存在すれば None を返す。

        :param image_path: 元画像のパス
        :param skip_suffix: スキップ対象のサフィックスリスト (例: ["final", "sample"])
        :return: None (スキップ条件に一致した場合) または 派生ファイルのリスト
        """
        if skip_suffix is None:
            skip_suffix = []

        base_name, ext = os.path.splitext(image_path)
        related_files = [
            f"{base_name}_{suffix}{ext}" for suffix in skip_suffix if os.path.exists(f"{base_name}_{suffix}{ext}")
        ]

        # サフィックスに一致するファイルが存在すれば None を返す
        if len(related_files) == len(skip_suffix):
            return None

        # 存在しない場合はチェックしたファイル名をリストで返す
        return related_files

class Filter:
    def apply(self, image_instance):
        raise NotImplementedError("Filter subclasses must implement the apply method.")


class FillLabelFilter(Filter):
    def __init__(self, fill_color=(255, 0, 255, 255)):
        self.fill_color = fill_color

    def apply(self, image_instance):
        fill_image = PILImage.new("RGBA", image_instance.image.size, self.fill_color)
        image_instance.image = PILImage.composite(fill_image, image_instance.image, image_instance.label_mask)

class ResizeFilter(Filter):
    def __init__(self, max_dimension=1000):
        """
        指定された最大辺の長さに基づいて画像をリサイズします。
        :param max_dimension: リサイズ後の最大辺の長さ（ピクセル単位）
        """
        self.max_dimension = max_dimension

    def apply(self, image_instance):
        """
        画像にリサイズフィルタを適用します。
        :param image_instance: リサイズ対象の画像を含むオブジェクト
        """
        if not image_instance.image:
            print("No image available for ResizeFilter.")
            return

        # 現在のサイズを取得
        original_width, original_height = image_instance.image.size

        # 縮小率を計算
        scale = min(self.max_dimension / original_width, self.max_dimension / original_height)

        # 新しいサイズを計算
        target_width = int(original_width * scale)
        target_height = int(original_height * scale)

        # 画像をリサイズ（最新の Pillow に対応）
        image_instance.image = image_instance.image.resize(
            (target_width, target_height),
            PILImage.Resampling.LANCZOS
        )

class LabelBlurFilter(Filter):
    def __init__(self, radius=5, mask_blur_radius=10):
        """
        Args:
            radius (int): ブラーの強度
            mask_blur_radius (int): マスクのぼかし強度
        """
        self.radius = radius
        self.mask_blur_radius = mask_blur_radius

    def apply(self, image_instance):
        """ラベル領域にブラーを適用し、境界を滑らかにする"""
        if not image_instance.label_mask:
            print("No label mask available for LabelBlurFilter.")
            return

        # 1. 元画像全体にブラーを適用
        blurred_image = image_instance.image.filter(ImageFilter.GaussianBlur(self.radius))

        # 2. マスクの境界をぼかす
        blurred_mask = image_instance.label_mask.filter(ImageFilter.GaussianBlur(self.mask_blur_radius))

        # 3. マスクを使ってラベル領域のみにブラーを適用
        image_instance.image = PILImage.composite(blurred_image, image_instance.image, blurred_mask)


from PIL import Image as PILImage, ImageDraw, ImageFilter
import numpy as np

class MosaicFilter(Filter):
    def __init__(self, ratio=0.1, resample_method=PILImage.NEAREST):
        """
        Args:
            ratio (float): 縮小率。小さいほどモザイクが粗くなる。
            resample_method (int): PIL.Image のリサンプル方法。
                利用可能なリサンプル方法:
                - PIL.Image.NEAREST (最も近いピクセル、デフォルト)
                - PIL.Image.BOX (ボックスフィルタ)
                - PIL.Image.BILINEAR (バイリニア補間)
                - PIL.Image.HAMMING (ハミングフィルタ)
                - PIL.Image.BICUBIC (バイキュービック補間)
                - PIL.Image.LANCZOS (ランチョスフィルタ)
        """
        self.ratio = ratio
        self.resample_method = resample_method

    def apply(self, image_instance):
        """
        ラベル領域にのみモザイクを適用します。
        """
        if not image_instance.label_mask:
            print("No label mask available for MosaicFilter.")
            return

        # モザイク処理を適用した画像を生成
        mosaic_image = self._mosaic(image_instance.image, self.ratio)

        # ラベルマスクを使用して、ラベル領域にのみモザイクを適用
        image_instance.image = PILImage.composite(mosaic_image, image_instance.image, image_instance.label_mask)

    def _mosaic(self, pil_image, ratio):
        """
        画像全体にモザイクを適用します。

        Args:
            pil_image (PIL.Image.Image): 入力画像
            ratio (float): 縮小率

        Returns:
            PIL.Image.Image: モザイク処理済み画像
        """
        # 画像のサイズを取得
        width, height = pil_image.size

        # 縮小サイズを計算（最小1ピクセル）
        mosaic_width = max(1, int(width * ratio))
        mosaic_height = max(1, int(height * ratio))

        # 画像を縮小（モザイクの粗さを決定）
        small = pil_image.resize((mosaic_width, mosaic_height), resample=self.resample_method)

        # 縮小した画像を元のサイズに拡大
        mosaic = small.resize((width, height), resample=self.resample_method)

        return mosaic
class WatermarkFilter(Filter):
    def __init__(self, text="Sample", font_path="./material/Gidole-Regular.ttf", alpha=0.3, size=15):
        self.text = text
        self.font_path = font_path
        self.alpha = alpha  # 透明度（0.0～1.0）
        self.size = size

    def apply(self, image_instance):
        """画面中央にウォーターマークを追加"""
        # 画像をRGBAモードに変換
        image = image_instance.image.convert("RGBA")
        width, height = image.size
        min_dim = min(width, height)
        font_size = int(min_dim * self.size/100)  # 画像の短辺の15%
        
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except IOError:
            print(f"フォントファイルが見つかりません: {self.font_path}")
            font = ImageFont.load_default()

        # ウォーターマークに表示するテキスト
        text = f"{self.text}\n({width} x {height})"

        # テキストのサイズを取得
        dummy_img = Image.new("RGBA", (width, height), (0,0,0,0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        text_bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # テキストの中央位置を計算
        x = (width - text_width) / 2
        y = (height - text_height) / 2

        # テキスト描画用の透明なレイヤーを作成
        text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.multiline_text(
            (x, y),
            text,
            font=font,
            fill=(255, 255, 255, int(255 * self.alpha)),
            align="center"
        )

        # 元の画像とテキストレイヤーを合成
        combined = Image.alpha_composite(image, text_layer).convert("RGB")
        image_instance.image = combined  # 元のインスタンスに戻す

import glob
import re
from tqdm import tqdm
from PIL import PngImagePlugin
import shutil


LARGE_ENOUGH_NUMBER = 100
PngImagePlugin.MAX_TEXT_CHUNK = LARGE_ENOUGH_NUMBER * (1024**2)

def process_images(file_list, override=False):
    """画像に対してフィルタを順に適用し、保存する"""
    for file_path in tqdm(file_list, desc="Processing Images", unit="file"):
        # 派生ファイルが存在する場合はスキップ
        is_exists = MyImage._get_related_files(file_path, skip_suffix=["submission", "sample"])
        if is_exists is None and not override:
            continue

        # 画像をロード

        # try:
        image = MyImage(file_path, padding=3)
        
        # フィルタを順に適用して保存
        image.apply_filter(MosaicFilter(ratio=0.1, resample_method=PILImage.BOX)) \
             .save("submission")

        # サンプル画像
        # image.apply_filter(MosaicFilter(ratio=0.004)) \
        #      .apply_filter(WatermarkFilter(size=10)) \
        #      .apply_filter(ResizeFilter(500)) \
        #      .save("sample")
        image.apply_filter(WhiteFillRotatedRectExpandedFilter(expand_px=80)) \
             .apply_filter(WatermarkFilter(size=10)) \
             .apply_filter(ResizeFilter(500)) \
             .save("sample")
        
        del image
        # except ResolutionError as e:
            # print(e)
            # move_related_files(file_path, delete_dir)

from PIL import Image as PILImage
from PIL import ImageFilter, ImageChops

class WhiteFillBlurFilter(Filter):
    def __init__(self, blur_radius=5):
        """
        Args:
            blur_radius (int, float): ラベル領域の境界に対して適用するガウスぼかしの半径
        """
        self.blur_radius = blur_radius

    def apply(self, image_instance):
        """
        ラベル領域は白く塗りつぶしつつ、
        境界部分だけをぼかして自然にマスクをなじませます。
        """
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillBlurFilter.")
            return

        # 真っ白な塗りつぶし用画像を作成
        white_image = PILImage.new("RGB", image_instance.image.size, (255, 255, 255))

        # ラベルマスクをグレースケール(Lモード)に変換
        label_mask_l = image_instance.label_mask.convert("L")

        # ガウスぼかしを適用
        blurred_mask = label_mask_l.filter(ImageFilter.GaussianBlur(self.blur_radius))

        # もとのマスクとぼかしたマスクを比較し、明るい方(白側)を採用
        # これでラベル領域は完全に白(=255)を保ちつつ、境界を部分的にぼかせる
        final_mask = ImageChops.lighter(label_mask_l, blurred_mask)

        # 白一色の画像と元画像を、合成マスク(final_mask)で合成
        # ラベル領域：白イメージ 100%
        # ラベル領域外：オリジナル画像
        # ラベル境界：部分的に白をブレンド
        image_instance.image = PILImage.composite(white_image, image_instance.image, final_mask)


def move_related_files(file_path, destination_dir):
    """
    指定されたファイルとその派生ファイルを指定フォルダに移動する
    """
    base_path, ext = os.path.splitext(file_path)
    related_files = glob.glob(f"{base_path}_*{ext}") + [file_path]

    for file in related_files:
        shutil.move(file, os.path.join(destination_dir, os.path.basename(file)))


from PIL import Image as PILImage
from PIL import ImageFilter, ImageChops
import cv2

class WhiteFillBlurFilter(Filter):
    def __init__(self, blur_radius=5, expand_px=3):
        """
        Args:
            blur_radius (int, float): ガウスぼかし半径
            expand_px (int): マスクを外側に拡張するピクセル数
        """
        self.blur_radius = blur_radius
        self.expand_px = expand_px

    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillBlurFilter.")
            return

        # label_mask を L (8bitグレースケール) に変換
        label_mask_l = image_instance.label_mask.convert("L")
        
        # 元のマスクも保持しておく(後で lighter 合成に使うため)
        original_mask_l = label_mask_l.copy()

        # ========== (1) マスクを拡張 (1回だけ) ==========
        # カーネルサイズ = 2 * expand_px + 1
        # 例) expand_px=3 なら MaxFilter(7)
        label_mask_l = label_mask_l.filter(ImageFilter.MaxFilter(2 * self.expand_px + 1))

        # ========== (2) ガウスぼかし ==========
        blurred_mask = label_mask_l.filter(ImageFilter.GaussianBlur(self.blur_radius))

        # ========== (3) lighter 合成で、元のマスク領域は必ず白を維持しつつ境界をブレンド ==========
        final_mask = ImageChops.lighter(original_mask_l, blurred_mask)

        # ========== (4) 白い画像と合成 ==========
        #   - ラベル内部は必ず白
        #   - 拡張ぼかしをかけた境界は最終マスクに応じて徐々に白がブレンド
        #   - ラベル領域外はオリジナル画像を残す
        white_image = PILImage.new("RGB", image_instance.image.size, (255, 255, 255))
        image_instance.image = PILImage.composite(white_image, image_instance.image, final_mask)


import numpy as np
import cv2
from PIL import Image as PILImage
from PIL import ImageChops

class WhiteFillBlurFilterCV2(Filter):
    def __init__(self, blur_sigma=5, expand_px=3):
        """
        Args:
            blur_sigma (float): ガウスぼかし用シグマ (標準偏差)
            expand_px (int): マスクの外側へ拡張するピクセル数
        """
        self.blur_sigma = blur_sigma
        self.expand_px = expand_px

    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillBlurFilterCV2.")
            return

        # === 0) 必要な準備 ===
        # 白塗り用の画像 (元画像サイズと同じ, 白で塗りつぶし)
        white_image = PILImage.new("RGB", image_instance.image.size, (255, 255, 255))

        # ラベルマスクをグレースケールにして numpy 配列化 (0～255)
        label_mask_l = image_instance.label_mask.convert("L")
        mask_array = np.array(label_mask_l, dtype=np.uint8)

        # 2値化 (閾値128以上でマスク有効ピクセルとみなす)
        # ※ すでにラベル領域が真っ白(255) であれば省略可
        _, bin_mask = cv2.threshold(mask_array, 128, 255, cv2.THRESH_BINARY)

        # === 1) モルフォロジー拡張 (dilate) で外側に expand_px 分だけ広げる ===
        kernel_size = 2 * self.expand_px + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        expanded = cv2.dilate(bin_mask, kernel, iterations=1)

        # === 2) ガウスぼかし ===
        # ksize=(0, 0) にしておけば、引数 sigmaX= self.blur_sigma で自動計算される
        # 例) sigmaX=5 ならそこそこのぼかしになる
        blurred = cv2.GaussianBlur(expanded, (0, 0), self.blur_sigma)

        # === 3) 元マスク( bin_mask ) と ぼかし後( blurred ) を比較して
        #        大きい方(明るい方)を採用 => ラベル領域(=255) は必ず白を維持
        lighter = np.maximum(bin_mask, blurred).astype(np.uint8)

        # === 4) numpy配列を PIL.Image に戻す ===
        final_mask = PILImage.fromarray(lighter, mode="L")

        # === 5) 白画像と元画像を合成 (ラベル領域→白, 境界はぼかしでなじませる) ===
        image_instance.image = PILImage.composite(white_image, image_instance.image, final_mask)


import numpy as np
import cv2
from PIL import Image as PILImage

class WhiteFillRectFilter(Filter):
    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillRectFilter.")
            return

        # 1) 画像モードを RGBA に統一
        if image_instance.image.mode != "RGBA":
            image_instance.image = image_instance.image.convert("RGBA")

        # 2) label_mask も L(8bitグレースケール) に変換 → numpy配列化
        mask_gray = image_instance.label_mask.convert("L")
        mask_array = np.array(mask_gray, dtype=np.uint8)

        # 3) 2値化
        _, bin_mask = cv2.threshold(mask_array, 128, 255, cv2.THRESH_BINARY)

        # 4) 輪郭を抽出
        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 5) 元画像を numpy配列化 (RGBA, shape: (H, W, 4))
        img_array = np.array(image_instance.image)

        # 6) 最小外接長方形を白塗り (RGBA)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # RGBA なので (255,255,255,255) の4要素
            img_array[y : y + h, x : x + w] = (255, 255, 255, 255)

        # 7) 塗り終わった配列を再度 PIL Image に戻す (RGBA)
        image_instance.image = PILImage.fromarray(img_array, mode="RGBA")

import numpy as np
import cv2
from PIL import Image as PILImage

class WhiteFillRotatedRectFilter(Filter):
    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillRotatedRectFilter.")
            return

        # 1) 画像を一律で RGB 化 (もしくは RGBA 化したければ適宜変更)
        if image_instance.image.mode != "RGB":
            image_instance.image = image_instance.image.convert("RGB")

        # 2) ラベルマスクをグレースケール(L)にして numpy配列化
        mask_gray = image_instance.label_mask.convert("L")
        mask_array = np.array(mask_gray, dtype=np.uint8)

        # 3) 2値化
        _, bin_mask = cv2.threshold(mask_array, 128, 255, cv2.THRESH_BINARY)

        # 4) 輪郭を抽出 (最外輪郭のみ)
        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 5) 元画像を numpy配列 (H,W,3) に変換
        img_array = np.array(image_instance.image)

        # 6) 複数の輪郭に対して「回転してもいい最小外接長方形」を求め、塗りつぶし
        for cnt in contours:
            # 6-1) 回転を考慮した最小外接長方形を取得
            #      minAreaRect() -> ((cx, cy), (width, height), angle)
            rotated_rect = cv2.minAreaRect(cnt)

            # 6-2) 長方形4頂点を取得 (float座標) → int型へ
            box = cv2.boxPoints(rotated_rect)  # shape: (4,2)
            box = np.int0(box)  # 整数に丸める

            # 6-3) 得られた4頂点で多角形を塗りつぶし(= 白)
            cv2.fillPoly(img_array, [box], (255, 255, 255))

        # 7) 塗り終わった配列を PIL 画像に戻して image_instance.image を更新
        image_instance.image = PILImage.fromarray(img_array, mode="RGB")

import numpy as np
import cv2
from PIL import Image as PILImage

class WhiteFillRotatedRectExpandedFilter(Filter):
    def __init__(self, expand_px=5):
        """
        Args:
            expand_px (int): マスクを外側に膨張させるピクセル数
        """
        self.expand_px = expand_px

    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillRotatedRectExpandedFilter.")
            return

        # 1) 画像は RGB 化しておく (4chなら RGBA にする)
        if image_instance.image.mode != "RGB":
            image_instance.image = image_instance.image.convert("RGB")

        # 2) ラベルマスクをグレースケール化 → numpy配列 (0 or 255)
        mask_gray = image_instance.label_mask.convert("L")
        mask_array = np.array(mask_gray, dtype=np.uint8)

        # 2値化
        _, bin_mask = cv2.threshold(mask_array, 128, 255, cv2.THRESH_BINARY)

        # 3) 膨張カーネル (楕円形など) を生成して外側に 'expand_px' 分だけ膨張
        #    カーネルサイズは (2*expand_px+1) x (2*expand_px+1)
        kernel_size = 2 * self.expand_px + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        dilated_mask = cv2.dilate(bin_mask, kernel, iterations=1)

        # 4) 膨張後マスクの輪郭を抽出
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 5) 元画像を numpy配列に
        img_array = np.array(image_instance.image)

        # 6) 各輪郭に対し最小外接回転長方形を求め、塗りつぶす
        for cnt in contours:
            rotated_rect = cv2.minAreaRect(cnt)
            box = cv2.boxPoints(rotated_rect)
            box = np.int0(box)  # 整数化
            cv2.fillPoly(img_array, [box], (255, 255, 255))

        # 7) 結果をPILに戻して反映
        image_instance.image = PILImage.fromarray(img_array, mode="RGB")


import numpy as np
import cv2
from PIL import Image as PILImage

class WhiteFillRotatedRectExpandedFilter(Filter):
    def __init__(self, expand_px=5):
        """
        Args:
            expand_px (int): 回転最小外接長方形をローカル座標系で expand_pxピクセルずつ拡張する
        """
        self.expand_px = expand_px

    def apply(self, image_instance):
        if not image_instance.label_mask:
            print("No label mask available for WhiteFillRotatedRectExpandedFilter.")
            return

        # 画像を RGB 化
        if image_instance.image.mode != "RGB":
            image_instance.image = image_instance.image.convert("RGB")

        # ラベルマスクを2値化
        mask_gray = image_instance.label_mask.convert("L")
        mask_array = np.array(mask_gray, dtype=np.uint8)
        _, bin_mask = cv2.threshold(mask_array, 128, 255, cv2.THRESH_BINARY)

        # 輪郭抽出 (外側のみ)
        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Pillow画像→Numpy配列
        img_array = np.array(image_instance.image)

        for cnt in contours:
            # (1) minAreaRect() で回転最小外接長方形を得る
            ((cx, cy), (w, h), angle) = cv2.minAreaRect(cnt)

            # (2) w, h を expand_px 分だけ拡張
            w_expanded = w + 2 * self.expand_px
            h_expanded = h + 2 * self.expand_px

            # (3) 拡張後の長方形を再定義
            rect_expanded = ((cx, cy), (w_expanded, h_expanded), angle)

            # (4) boxPoints() で四隅の座標を取得 → 整数化
            box_expanded = cv2.boxPoints(rect_expanded)
            box_expanded = np.int0(box_expanded)

            # (5) fillPoly() で塗りつぶし
            cv2.fillPoly(img_array, [box_expanded], (0, 0, 0))

        # 処理結果を PIL Image に戻す
        image_instance.image = PILImage.fromarray(img_array, "RGB")

