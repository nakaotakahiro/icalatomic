import errno
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO, Any, Literal, Union

__all__ = ["atomic_write"]


@contextmanager
def atomic_write(
    path: Union[str, os.PathLike[str]],
    mode: Literal["w", "wt", "wb", "x", "xt", "xb"],
    *args: Any,
    **kwargs: Any,
) -> Iterator[IO[Any]]:
    # ファイル作成以外のmodeが渡されたら弾く
    if mode not in ("w", "wt", "wb", "x", "xt", "xb"):
        raise ValueError(f"Expected 'w', 'wt', 'wb', 'x', 'xt' or 'xb', got {mode!r}")
    exclusive = mode.startswith("x")  # x: 排他モード (出力先にファイルが存在すると失敗)

    # ディレクトリらしいパスをあらかじめ弾いておく
    # Path(path)は末尾のスラッシュなどをstripしてしまうので、弾いておかないと後続のコードがそのまま通ってしまう
    # (たとえば、atomic_write("foo/") で "foo" を出力/上書きできてしまう)
    if os.path.basename(path) in ("", ".", ".."):
        raise ValueError(f"Expected a file name, got {path!r}")

    # 先に相対パスを解決しておく (長い書き込み中にカレントディレクトリが変わると出力先がずれるので)
    destination = Path(path).absolute()

    # 排他モードのときは先に存在を確認しておく (存在すれば最後の os.link() で失敗するはずだが、時短のため)
    if exclusive and os.path.lexists(destination):
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), path)

    with TemporaryDirectory(dir=destination.parent) as directory:
        # 出力先と同じファイルシステムの一時ファイルに書き出し
        temporary_path = Path(directory) / destination.name
        with open(temporary_path, mode, *args, **kwargs) as file:
            yield file

        # 出力が完了してから、一時ファイルをatomicに出力先に配置
        if exclusive:
            # 排他モード (x) なら、os.link() でハードリンクを作成 (→ 一時ファイル側は自動削除)
            # ハードリンク作成先にファイルがあればFileExistsErrorになる
            os.link(temporary_path, destination)
        else:
            # 上書きモード (w) なら、os.replace() で出力先に移動
            # 出力先が存在しても上書きされる
            try:
                # 出力先が既にあれば、そのパーミッションを保持 (標準のopen()の挙動に合わせる)
                shutil.copymode(destination, temporary_path)
            except FileNotFoundError:
                pass
            os.replace(temporary_path, destination)
