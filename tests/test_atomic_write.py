import os
import stat

import pytest

from icalatomic import atomic_write


def test_create_text_file(tmp_path):
    path = tmp_path / "result.txt"
    with atomic_write(str(path), "x", encoding="utf-8") as file:
        file.write("東京")
        assert not path.exists()
    assert path.read_text(encoding="utf-8") == "東京"
    assert list(tmp_path.iterdir()) == [path]


def test_overwrite_binary_file(tmp_path):
    path = tmp_path / "result.bin"
    path.write_bytes(b"original")
    with atomic_write(path, "wb") as file:
        file.write(b"\x00\xff")
        file.flush()
        assert path.read_bytes() == b"original"
    assert path.read_bytes() == b"\x00\xff"
    assert list(tmp_path.iterdir()) == [path]


# Windows の chmod は読み取り専用属性しか変更しない
posix_permissions_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")

# open() が作るファイルには実行ビットが付かないため、
# 実行ビットを含むパーミッションなら umask によらず既定のパーミッションと区別できる
DISTINCT_PERMISSIONS = [0o700, 0o755]


@posix_permissions_only
@pytest.mark.parametrize("permissions", DISTINCT_PERMISSIONS, ids=oct)
def test_overwrite_keeps_permissions(tmp_path, permissions):
    path = tmp_path / "result"
    path.write_text("original")
    path.chmod(permissions)
    with atomic_write(path, "w") as file:
        file.write("new")
    assert path.read_text() == "new"
    assert stat.S_IMODE(path.stat().st_mode) == permissions


@posix_permissions_only
@pytest.mark.parametrize("permissions", DISTINCT_PERMISSIONS, ids=oct)
def test_overwrite_symlink_uses_target_permissions(tmp_path, permissions):
    target = tmp_path / "target"
    target.write_text("original")
    target.chmod(permissions)
    path = tmp_path / "link"
    path.symlink_to(target)
    with atomic_write(path, "w") as file:
        file.write("new")
    assert path.read_text() == "new"
    assert stat.S_IMODE(path.stat().st_mode) == permissions


def test_overwrite_missing_file_gets_default_permissions(tmp_path):
    path = tmp_path / "result"
    reference = tmp_path / "reference"
    reference.touch()
    with atomic_write(path, "w") as file:
        file.write("new")
    assert path.read_text() == "new"
    assert path.stat().st_mode == reference.stat().st_mode


@pytest.mark.parametrize("suffix", [os.sep, os.sep + "."])
def test_directory_suffix_cannot_overwrite_file(tmp_path, suffix):
    path = tmp_path / "result"
    path.write_text("original")

    with pytest.raises(ValueError), atomic_write(str(path) + suffix, "w"):
        pytest.fail("A directory path was accepted for writing")

    assert path.read_text() == "original"


def test_trailing_separator_cannot_create_file(tmp_path):
    path = tmp_path / "result"
    with pytest.raises(ValueError), atomic_write(str(path) + os.sep, "x"):
        pytest.fail("A directory path was accepted for writing")
    assert list(tmp_path.iterdir()) == []


def test_forwards_open_options(tmp_path):
    path = tmp_path / "result.txt"
    with atomic_write(path, "wt", -1, "ascii", errors="replace", newline="\r\n") as file:
        file.write("café\n")
    assert path.read_bytes() == b"caf?\r\n"


@pytest.mark.parametrize("mode", ["x", "xt", "xb"])
def test_exclusive_mode_fails_before_writing(tmp_path, mode):
    path = tmp_path / "existing"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError), atomic_write(path, mode):
        pytest.fail("Writing started although the destination exists")
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(os.name == "nt", reason="Creating symlinks requires privileges on Windows")
def test_exclusive_mode_treats_dangling_symlink_as_existing(tmp_path):
    path = tmp_path / "link"
    path.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError), atomic_write(path, "x"):
        pytest.fail("Writing started although the destination exists")
    assert list(tmp_path.iterdir()) == [path]


def test_first_completed_writer_wins(tmp_path):
    path = tmp_path / "result"
    with pytest.raises(FileExistsError), atomic_write(path, "x") as slow:
        slow.write("slow")
        with atomic_write(path, "x") as fast:
            fast.write("fast")
    assert path.read_text() == "fast"
    assert list(tmp_path.iterdir()) == [path]


def test_interrupted_create(tmp_path):
    with pytest.raises(KeyboardInterrupt), atomic_write(tmp_path / "result", "x") as file:
        file.write("partial")
        raise KeyboardInterrupt
    assert list(tmp_path.iterdir()) == []


def test_interrupted_overwrite(tmp_path):
    path = tmp_path / "result"
    path.write_bytes(b"original")
    with pytest.raises(KeyboardInterrupt), atomic_write(path, "w") as file:
        file.write("partial")
        raise KeyboardInterrupt
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]


def test_unsupported_mode(tmp_path):
    with pytest.raises(ValueError, match="xb"), atomic_write(tmp_path / "file", "a"):
        pass
    assert list(tmp_path.iterdir()) == []
