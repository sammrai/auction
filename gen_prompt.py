import glob
import os
import fnmatch
import random
from typing import List, Optional

class ExtendedGlob:
    @staticmethod
    def glob(pattern: str, exclude: Optional[List[str]] = None, require: bool = False, recursive: bool = False) -> dict:
        """
        `glob.glob` を拡張して、除外パターンと必須オプションを指定できるようにした関数。

        :param pattern: 検索するファイルのパターン
        :param exclude: 除外するパターンのリスト（オプション）
        :param require: 必須の場合は True を指定
        :param recursive: 再帰的に検索するかどうか
        :return: 必須フラグとファイルリストを含む辞書
        """
        # 全ファイルを取得
        all_files = glob.glob(pattern, recursive=recursive)

        # 除外パターンが指定されていない場合、そのまま返す
        if exclude:
            all_files = [
                f for f in all_files if not any(fnmatch.fnmatch(f, ex) for ex in exclude)
            ]

        return {"files": all_files, "require": require}


def load_prompts_from_files(file_list: List[str], blacklist: Optional[List[str]] = None) -> List[List[str]]:
    """
    ファイルリストからプロンプトを読み込み、リスト化する。
    ブラックリストに含まれる単語を除外する。

    :param file_list: 読み込むファイルパスのリスト
    :param blacklist: ブラックリストに含まれる単語（オプション）
    :return: 各ファイルのプロンプトのリストを格納したリスト
    """
    prompts = []
    for file in file_list:
        if os.path.isfile(file):  # ファイルが存在するか確認
            with open(file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]  # 空行を除外
                if blacklist:
                    lines = [line for line in lines if not any(word in line for word in blacklist)]
                prompts.append(lines)
    return prompts



def generate_prompt_string(prompts: List[List[str]], requirements: List[bool]) -> str:
    """
    各リストからランダムにプロンプトを選択し、カンマで区切った文字列を生成する。

    :param prompts: 各ファイルのプロンプトのリストを格納したリスト
    :param requirements: 各リストが必須かどうかを示すブール値のリスト
    :return: 選択されたプロンプトをカンマで区切った文字列
    """
    result = []
    for prompt_list, is_required in zip(prompts, requirements):
        if is_required or (not is_required and random.choice([True, False])):
            result.append(random.choice(prompt_list))
    return ", ".join(result)


base = "sd-dynamic-prompts"

# 検索パターンと必須フラグを指定
file_configs = [
    # ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/pose/posture_*"), exclude=["*two*", "*three*", "*hugg*", "*each*"]),
    # ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/composition/image_composition_angle_perspective_depth.txt"), ),
    ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/clothes/swimsuit_male*"), ),
    ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/attire/attire_traditional_clothing.txt"),require=True),
    ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/body-1/eyes_gazes.txt"), require=True),
    ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/pose/posture_other_whole_body.txt"), require=True),
    ExtendedGlob.glob(os.path.join(base, "collections/devilkkw/body-1/hair_facial.txt"), require=True),
    ExtendedGlob.glob(os.path.join(base, "location.txt"), require=True),
    ExtendedGlob.glob(os.path.join(base, "angles.txt"), require=True),
]

# ファイルリストと必須フラグを分離
all_files = [config["files"] for config in file_configs]
requirements = [config["require"] for config in file_configs]

# 各ファイルのプロンプトを読み込み
flat_file_list = []
flat_requirements = []


# 禁止ワードリスト（ブラックリスト）
blacklist = ["girl", "fake", "phone", "inugami"]


for file_list, require in zip(all_files, requirements):
    flat_file_list.extend(file_list)  # ファイルリストをフラット化
    flat_requirements.extend([require] * len(file_list))  # 対応する require を拡張


# すべてのプロンプトを読み込む（ブラックリストを適用）
prompts = load_prompts_from_files(flat_file_list, blacklist=blacklist)

assert len(prompts) == len(requirements)

def random_prompt():
# プロンプト文字列を生成
    prompt_string = generate_prompt_string(prompts, flat_requirements)
    return (prompt_string)
