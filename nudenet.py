import os
import _io
import math
import cv2
import numpy as np
import onnxruntime
from onnxruntime.capi import _pybind_state as C
from enum import Enum

__labels = [
    "FEMALE_GENITALIA_COVERED",
    "FACE_FEMALE",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "ANUS_EXPOSED",
    "FEET_EXPOSED",
    "BELLY_COVERED",
    "FEET_COVERED",
    "ARMPITS_COVERED",
    "ARMPITS_EXPOSED",
    "FACE_MALE",
    "BELLY_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
]


class NudeLabels(Enum):
    FEMALE_GENITALIA_COVERED = "FEMALE_GENITALIA_COVERED"
    FACE_FEMALE = "FACE_FEMALE"
    BUTTOCKS_EXPOSED = "BUTTOCKS_EXPOSED"
    FEMALE_BREAST_EXPOSED = "FEMALE_BREAST_EXPOSED"
    FEMALE_GENITALIA_EXPOSED = "FEMALE_GENITALIA_EXPOSED"
    MALE_BREAST_EXPOSED = "MALE_BREAST_EXPOSED"
    ANUS_EXPOSED = "ANUS_EXPOSED"
    FEET_EXPOSED = "FEET_EXPOSED"
    BELLY_COVERED = "BELLY_COVERED"
    FEET_COVERED = "FEET_COVERED"
    ARMPITS_COVERED = "ARMPITS_COVERED"
    ARMPITS_EXPOSED = "ARMPITS_EXPOSED"
    FACE_MALE = "FACE_MALE"
    BELLY_EXPOSED = "BELLY_EXPOSED"
    MALE_GENITALIA_EXPOSED = "MALE_GENITALIA_EXPOSED"
    ANUS_COVERED = "ANUS_COVERED"
    FEMALE_BREAST_COVERED = "FEMALE_BREAST_COVERED"
    BUTTOCKS_COVERED = "BUTTOCKS_COVERED"


def _read_image(image_path, target_size=320):
    if isinstance(image_path, str):
        mat = cv2.imread(image_path)
    elif isinstance(image_path, np.ndarray):
        mat = image_path
    elif isinstance(image_path, bytes):
        mat = cv2.imdecode(np.frombuffer(image_path, np.uint8), -1)
    elif isinstance(image_path, _io.BufferedReader):
        mat = cv2.imdecode(np.frombuffer(image_path.read(), np.uint8), -1)
    else:
        raise ValueError(
            "please make sure the image_path is str or np.ndarray or bytes"
        )

    image_original_width, image_original_height = mat.shape[1], mat.shape[0]

    mat_c3 = cv2.cvtColor(mat, cv2.COLOR_RGBA2BGR)

    max_size = max(mat_c3.shape[:2])  # get max size from width and height
    x_pad = max_size - mat_c3.shape[1]  # set xPadding
    x_ratio = max_size / mat_c3.shape[1]  # set xRatio
    y_pad = max_size - mat_c3.shape[0]  # set yPadding
    y_ratio = max_size / mat_c3.shape[0]  # set yRatio

    mat_pad = cv2.copyMakeBorder(mat_c3, 0, y_pad, 0, x_pad, cv2.BORDER_CONSTANT)

    input_blob = cv2.dnn.blobFromImage(
        mat_pad,
        1 / 255.0,  # normalize
        (target_size, target_size),  # resize to model input size
        (0, 0, 0),  # mean subtraction
        swapRB=True,  # swap red and blue channels
        crop=False,  # don't crop
    )

    return (
        input_blob,
        x_ratio,
        y_ratio,
        x_pad,
        y_pad,
        image_original_width,
        image_original_height,
    )


def _postprocess(
    output,
    x_pad,
    y_pad,
    x_ratio,
    y_ratio,
    image_original_width,
    image_original_height,
    model_width,
    model_height,
):
    outputs = np.transpose(np.squeeze(output[0]))
    rows = outputs.shape[0]
    boxes = []
    scores = []
    class_ids = []

    for i in range(rows):
        classes_scores = outputs[i][4:]
        max_score = np.amax(classes_scores)

        if max_score >= 0.2:
            class_id = np.argmax(classes_scores)
            x, y, w, h = outputs[i][0:4]

            # Convert from center coordinates to top-left corner coordinates
            x = x - w / 2
            y = y - h / 2

            # Scale coordinates to original image size
            x = x * (image_original_width + x_pad) / model_width
            y = y * (image_original_height + y_pad) / model_height
            w = w * (image_original_width + x_pad) / model_width
            h = h * (image_original_height + y_pad) / model_height

            # Remove padding
            x = x
            y = y

            # Clip coordinates to image boundaries
            x = max(0, min(x, image_original_width))
            y = max(0, min(y, image_original_height))
            w = min(w, image_original_width - x)
            h = min(h, image_original_height - y)

            class_ids.append(class_id)
            scores.append(max_score)
            boxes.append([x, y, w, h])

    indices = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45)

    detections = []
    for i in indices:
        box = boxes[i]
        score = scores[i]
        class_id = class_ids[i]

        x, y, w, h = box
        detections.append(
            {
                "class": NudeLabels(__labels[class_id]),
                "score": float(score),
                "box": [int(x), int(y), int(w), int(h)],
            }
        )

    return detections


class NudeDetector:
    def __init__(self, model_path="models/640m.onnx", providers=None, inference_resolution=640):
        self.onnx_session = onnxruntime.InferenceSession(model_path)
        model_inputs = self.onnx_session.get_inputs()

        self.input_width = inference_resolution
        self.input_height = inference_resolution
        self.input_name = model_inputs[0].name

    def detect(self, image_path):
        (
            preprocessed_image,
            x_ratio,
            y_ratio,
            x_pad,
            y_pad,
            image_original_width,
            image_original_height,
        ) = _read_image(image_path, self.input_width)
        outputs = self.onnx_session.run(None, {self.input_name: preprocessed_image})
        detections = _postprocess(
            outputs,
            x_pad,
            y_pad,
            x_ratio,
            y_ratio,
            image_original_width,
            image_original_height,
            self.input_width,
            self.input_height,
        )

        return detections

    def detect_batch(self, image_paths, batch_size=4):
        """
        Perform batch detection on a list of images.

        Args:
            image_paths (List[Union[str, np.ndarray]]): List of image paths or numpy arrays.
            batch_size (int): Number of images to process in each batch.

        Returns:
            List of detection results for each image.
        """
        all_detections = []

        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i : i + batch_size]
            batch_inputs = []
            batch_metadata = []

            for image_path in batch:
                (
                    preprocessed_image,
                    x_ratio,
                    y_ratio,
                    x_pad,
                    y_pad,
                    image_original_width,
                    image_original_height,
                ) = _read_image(image_path, self.input_width)
                batch_inputs.append(preprocessed_image)
                batch_metadata.append(
                    (
                        x_ratio,
                        y_ratio,
                        x_pad,
                        y_pad,
                        image_original_width,
                        image_original_height,
                    )
                )

            # Stack the preprocessed images into a single numpy array
            batch_input = np.vstack(batch_inputs)

            # Run inference on the batch
            outputs = self.onnx_session.run(None, {self.input_name: batch_input})

            # Process the outputs for each image in the batch
            for j, metadata in enumerate(batch_metadata):
                (
                    x_ratio,
                    y_ratio,
                    x_pad,
                    y_pad,
                    image_original_width,
                    image_original_height,
                ) = metadata
                detections = _postprocess(
                    [outputs[0][j : j + 1]],  # Select the output for this image
                    x_pad,
                    y_pad,
                    x_ratio,
                    y_ratio,
                    image_original_width,
                    image_original_height,
                    self.input_width,
                    self.input_height,
                )
                all_detections.append(detections)

        return all_detections

    def censor(self, image_path, classes=[], output_path=None):
        detections = self.detect(image_path)
        if classes:
            detections = [
                detection for detection in detections if detection["class"] in classes
            ]

        img = cv2.imread(image_path)

        for detection in detections:
            box = detection["box"]
            x, y, w, h = box[0], box[1], box[2], box[3]
            # change these pixels to pure black
            img[y : y + h, x : x + w] = (0, 0, 0)

        if not output_path:
            image_path, ext = os.path.splitext(image_path)
            output_path = f"{image_path}_censored{ext}"

        cv2.imwrite(output_path, img)

        return output_path



LABEL_COLORS = {
    # マゼンタ
    NudeLabels.ANUS_EXPOSED: (255,0,255),
    NudeLabels.MALE_GENITALIA_EXPOSED: (0, 255, 0),      # 鮮やかな赤

    # 性器関連
    NudeLabels.FEMALE_GENITALIA_COVERED: (200, 162, 200),  # 薄い紫（カバー部分）
    NudeLabels.FEMALE_GENITALIA_EXPOSED: (255, 0, 255),   # 鮮やかな紫（露出部分）

    # 肛門関連
    NudeLabels.ANUS_COVERED: (255, 222, 173),            # ベージュ（カバー部分）

    # 胸部関連
    NudeLabels.FEMALE_BREAST_EXPOSED: (255, 20, 147),    # ピンク（女性胸部露出）
    NudeLabels.FEMALE_BREAST_COVERED: (240, 230, 140),  # カーキ（女性胸部カバー）
    NudeLabels.MALE_BREAST_EXPOSED: (30, 144, 255),     # 青（男性胸部露出）

    # お尻関連
    NudeLabels.BUTTOCKS_COVERED: (222, 184, 135),       # ベージュ
    NudeLabels.BUTTOCKS_EXPOSED: (139, 69, 19),        # 茶色（露出）

    # 顔
    NudeLabels.FACE_FEMALE: (255, 182, 193),           # ピンク（女性顔）
    NudeLabels.FACE_MALE: (70, 130, 180),             # 青（男性顔）

    # 足や体の部位
    NudeLabels.FEET_EXPOSED: (244, 164, 96),          # サンドブラウン（露出）
    NudeLabels.FEET_COVERED: (144, 238, 144),         # ライトグリーン（カバー）

    NudeLabels.BELLY_COVERED: (173, 216, 230),        # ライトブルー（お腹カバー）
    NudeLabels.BELLY_EXPOSED: (255, 160, 122),        # サーモン（お腹露出）

    # 脇
    NudeLabels.ARMPITS_COVERED: (176, 224, 230),      # パウダーブルー（カバー）
    NudeLabels.ARMPITS_EXPOSED: (135, 206, 235),      # スカイブルー（露出）
}


import requests
import io
from PIL import Image
import cv2
import matplotlib.pyplot as plt

class ImageInferencer:
    def __init__(self, url):
        self.url = url

    def infer(self, file_path):
        # 推論前にPILで横長チェック → 画像を回転 → メモリ上に保存して送信
        with Image.open(file_path) as pil_img:
            width, height = pil_img.size
            if width > height:
                # PIL では 90 度は「反時計回り」
                pil_img = pil_img.rotate(90, expand=True)

            with io.BytesIO() as buffer:
                pil_img.save(buffer, format="JPEG")
                buffer.seek(0)
                files = {"f1": ("rotated.jpg", buffer, "image/jpeg")}
                response = requests.post(self.url, files=files)

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result
            else:
                raise ValueError("Inference failed: API did not return success.")
        else:
            raise ConnectionError(f"Error {response.status_code}: {response.text}")

    def draw_predictions(self, image_path, predictions):
        # OpenCVで読み込み
        image = cv2.imread(image_path)
        # BGR -> RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 回転チェック: OpenCVでは (高さ, 幅) = image.shape[:2]
        h, w = image.shape[:2]
        if w > h:
            # OpenCV での回転はデフォルトが「時計回り」なので、PILと合わせるなら「COUNTERCLOCKWISE」
            image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # 推論結果のバウンディングボックスを描画
        for pred in predictions:
            cls = pred["class"]
            score = pred["score"]
            x, y, box_w, box_h = pred["box"]

            # ラベルごとの色を取得
            color = LABEL_COLORS.get(NudeLabels(cls), (255, 255, 255))

            # ボックスの描画
            cv2.rectangle(image, (x, y), (x + box_w, y + box_h), color, 5)

            # クラス名とスコアをテキスト表示
            label = f"{cls} ({score:.2f})"
            cv2.putText(image, label, (x, y + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)

        # 画像を表示
        plt.figure(figsize=(12, 8))
        plt.imshow(image)
        plt.axis("off")
        plt.show()


def save_labeled_image(file_path, labeled_file_path, predictions, target_classes=[NudeLabels.ANUS_EXPOSED, NudeLabels.MALE_GENITALIA_EXPOSED], show_image=False):
    """
    推論結果を描画し、塗りつぶして保存する関数。

    Args:
        file_path (str): 元画像のファイルパス。
        predictions (list): 推論結果のリスト。
        target_classes (list): 塗りつぶし対象のクラスのリスト。
        show_image (bool): 画像を表示するかどうか（デフォルトはFalse）。

    Returns:
        str: 保存した画像のファイルパス。
    """
    # 画像を読み込み
    img = cv2.imread(file_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # OpenCVはBGRなのでRGBに変換
    img_height, img_width, _ = img.shape

    # 画像全体を半分白くする（露出調整）
    white_overlay = np.ones_like(img, dtype=np.uint8) * 255
    alpha = 0.5
    img = cv2.addWeighted(img, 1 - alpha, white_overlay, alpha, 0)

    # 線幅を画像サイズに基づいて調整
    line_thickness = max(1, min(img_width, img_height) // 300)

    for pred in predictions:
        cls_label = pred.get("class", "Unknown")
        box = pred.get("box", [0, 0, 0, 0])

        if cls_label not in target_classes:
            continue

        x1, y1, width, height = box
        x2, y2 = x1 + width, y1 + height
        color = LABEL_COLORS.get(cls_label, (255, 0, 0))

        # 塗りつぶし処理
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness=-1)


    cv2.imwrite(labeled_file_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    # 画像表示（オプション）
    if show_image:
        plt.figure(figsize=(10, 10))
        plt.imshow(img)
        plt.axis('off')
        plt.show()

    return labeled_file_path


if __name__ == "__main__":
    detector = NudeDetector()
    # detections = detector.detect("/Users/praneeth.bedapudi/Desktop/cory.jpeg")
    print(
        detector.detect_batch(
            [
                "/Users/praneeth.bedapudi/Desktop/d.jpg",
                "/Users/praneeth.bedapudi/Desktop/a.jpeg",
            ]
        )[0]
    )
    print(detector.detect_batch(["/Users/praneeth.bedapudi/Desktop/d.jpg"])[0])

    print(
        detector.detect_batch(
            [
                "/Users/praneeth.bedapudi/Desktop/d.jpg",
                "/Users/praneeth.bedapudi/Desktop/a.jpeg",
            ]
        )[1]
    )
    print(detector.detect_batch(["/Users/praneeth.bedapudi/Desktop/a.jpeg"])[0])