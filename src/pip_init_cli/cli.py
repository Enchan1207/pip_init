#
# pip_init CLI
#
import importlib
from logging import handlers
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

import pip_init

from pip_init_cli.args_handler import ArgsHandlerBase
from pip_init_cli.config_loader import ConfigLoader


def main() -> int:
    # コマンドライン引数の設定
    parser = ArgumentParser(
        prog='pip_init',
        usage="%(prog)s [target] [--name name_of_template] [--template_dir path/to/template]",
        description="Python package template extractor")
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="template extract destination (Defaults to current directory)")
    parser.add_argument(
        "--name", "-n",
        default="default",
        help="name of template (Defaults to library internal template \"default\")")
    parser.add_argument(
        "--template_dir", "-t",
        help="template root directory (optional)")

    # パースして情報を取得
    args = parser.parse_args()
    extract_root: Path = Path(args.target).absolute()
    template_name: str = args.name
    additional_template_dir: Optional[Path] = Path(args.template_dir).absolute() if args.template_dir is not None else None

    # template_rootが指定された場合はsys.pathに追加しておく
    if additional_template_dir is not None:
        sys.path.append(str(additional_template_dir))
    # そうでなければ ~/.pip_init/をsys.pathに追加する
    # このディレクトリは存在してもしなくてもよい
    else:
        sys.path.append(str(Path.home() / ".pip_init"))

    # パスを解決し、テンプレートをimportする
    #  - template_root が None である: pip_init_internal_templates.{template_name} のインポートを試みる
    #  - template_root が None でない: pip_init_templates.{template_name} のインポートを試みる
    if additional_template_dir is None:
        template_import_path: str = f"pip_init_internal_templates.{template_name}"
    else:
        template_import_path = f"pip_init_templates.{template_name}"

    try:
        template_module = importlib.import_module(template_import_path)
    except ImportError:
        print("\033[31;1mfailed to import template! check if the path is valid.\033[0m")
        print(f"search path: \033[36m{template_import_path}\033[0m")
        return 1

    # importしたモジュールからテンプレートの親ディレクトリを特定し、template.jsonを読み込む
    template_root = Path(template_module.__file__).parent
    with open(template_root / "template.json") as f:
        template_json = f.read()
    config = ConfigLoader.load(template_json)

    # 引数ハンドラを特定する
    args_handler_name = config.args_handler_name or "__default__"
    args_handler_candidates = list(filter(lambda handler: handler.__handler_name__ == args_handler_name, ArgsHandlerBase.handlers))
    if len(args_handler_candidates) != 1:
        print("\033[31;1mcould not identify argument handler!\033[0m")
        return 1
    args_handler = args_handler_candidates[0]

    # 引数ハンドラに渡して値をセットしてもらう
    prepared_args = args_handler.handle_args(config.args)

    # Contentをビルド
    content_builder = pip_init.ContentBuilder(str(template_root), str(extract_root), prepared_args)
    prepared_contents = [content_builder.build(content) for content in config.contents]

    # 配置
    for content in prepared_contents:
        pip_init.ContentExtractor.extract(content)

    print("Succeeded.")
    return 0


if __name__ == "__main__":
    result = 0
    try:
        result = main() or 0
    except KeyboardInterrupt:
        print("Ctrl+C")
        exit(result)
