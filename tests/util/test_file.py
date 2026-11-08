"""Test Home Assistant file utility functions."""

import os
from pathlib import Path
from unittest.mock import patch

import py
import pytest

from homeassistant.util.file import (
    WriteError,
    safe_join,
    write_utf8_file,
    write_utf8_file_atomic,
)


@pytest.mark.parametrize("func", [write_utf8_file, write_utf8_file_atomic])
def test_write_utf8_file_atomic_private(tmpdir: py.path.local, func) -> None:
    """Test files can be written as 0o600 or 0o644."""
    test_dir = tmpdir.mkdir("files")
    test_file = Path(test_dir / "test.json")

    func(test_file, '{"some":"data"}', False)
    with open(test_file, encoding="utf8") as fh:
        assert fh.read() == '{"some":"data"}'
    assert os.stat(test_file).st_mode & 0o777 == 0o644

    func(test_file, '{"some":"data"}', True)
    with open(test_file, encoding="utf8") as fh:
        assert fh.read() == '{"some":"data"}'
    assert os.stat(test_file).st_mode & 0o777 == 0o600

    func(test_file, b'{"some":"data"}', True, mode="wb")
    with open(test_file, encoding="utf8") as fh:
        assert fh.read() == '{"some":"data"}'
    assert os.stat(test_file).st_mode & 0o777 == 0o600


def test_write_utf8_file_fails_at_creation(tmpdir: py.path.local) -> None:
    """Test that failed creation of the temp file does not create an empty file."""
    test_dir = tmpdir.mkdir("files")
    test_file = Path(test_dir / "test.json")

    with (
        pytest.raises(WriteError),
        patch(
            "homeassistant.util.file.tempfile.NamedTemporaryFile", side_effect=OSError
        ),
    ):
        write_utf8_file(test_file, '{"some":"data"}', False)

    assert not os.path.exists(test_file)


def test_write_utf8_file_fails_at_rename(
    tmpdir: py.path.local, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that if rename fails not not remove, we do not log the failed cleanup."""
    test_dir = tmpdir.mkdir("files")
    test_file = Path(test_dir / "test.json")

    with (
        pytest.raises(WriteError),
        patch("homeassistant.util.file.os.replace", side_effect=OSError),
    ):
        write_utf8_file(test_file, '{"some":"data"}', False)

    assert not os.path.exists(test_file)

    assert "File replacement cleanup failed" not in caplog.text


def test_write_utf8_file_fails_at_rename_and_remove(
    tmpdir: py.path.local, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that if rename and remove both fail, we log the failed cleanup."""
    test_dir = tmpdir.mkdir("files")
    test_file = Path(test_dir / "test.json")

    with (
        pytest.raises(WriteError),
        patch("homeassistant.util.file.os.remove", side_effect=OSError),
        patch("homeassistant.util.file.os.replace", side_effect=OSError),
    ):
        write_utf8_file(test_file, '{"some":"data"}', False)

    assert "File replacement cleanup failed" in caplog.text


@pytest.mark.parametrize("func", [write_utf8_file, write_utf8_file_atomic])
def test_write_utf8_file_with_non_ascii_content(tmp_path: Path, func) -> None:
    """Test files with non-ASCII content can be written even when locale is ASCII."""
    test_file = tmp_path / "test.json"
    non_ascii_data = '{"name":"自动化","emoji":"🏠"}'

    with patch("locale.getpreferredencoding", return_value="ascii"):
        func(test_file, non_ascii_data, False)

    file_text = test_file.read_text(encoding="utf-8")
    assert file_text == non_ascii_data


def test_write_utf8_file_atomic_fails(tmpdir: py.path.local) -> None:
    """Test OSError from write_utf8_file_atomic is rethrown as WriteError."""
    test_dir = tmpdir.mkdir("files")
    test_file = Path(test_dir / "test.json")

    with (
        pytest.raises(WriteError),
        patch("homeassistant.util.file.AtomicWriter.open", side_effect=OSError),
    ):
        write_utf8_file_atomic(test_file, '{"some":"data"}', False)

    assert not os.path.exists(test_file)


@pytest.mark.parametrize(
    ("base", "parts", "expected"),
    [
        pytest.param("/base", ("a",), "/base/a", id="single"),
        pytest.param("/base", ("a/b.yaml",), "/base/a/b.yaml", id="nested"),
        pytest.param("/base", ("a", "b"), "/base/a/b", id="multiple_parts"),
        pytest.param("/base", ("a/b/../../c",), "/base/c", id="dotdot_inside"),
        pytest.param("/base", ("../base/x",), "/base/x", id="dotdot_back_into_base"),
        pytest.param(Path("/base"), ("a",), "/base/a", id="path_base"),
        pytest.param("/base", ("...",), "/base/...", id="three_dots"),
        pytest.param("/base", ("%2e%2e",), "/base/%2e%2e", id="percent_encoded"),
        pytest.param("/base", ("..\\x",), "/base/..\\x", id="backslash"),
        pytest.param("/base", ("~",), "/base/~", id="tilde"),
        pytest.param("/base", ("",), "/base", id="empty_returns_base"),
        pytest.param("/base", (".",), "/base", id="dot_returns_base"),
    ],
)
def test_safe_join(base: str | Path, parts: tuple[str, ...], expected: str) -> None:
    """Test that safe_join returns the path in the base folder."""
    assert safe_join(base, *parts) == Path(expected)


@pytest.mark.parametrize(
    ("base", "parts"),
    [
        pytest.param("/base", ("../x",), id="parent"),
        pytest.param("/base", ("..",), id="parent_only"),
        pytest.param("/base", ("a/../../x",), id="nested_escape"),
        pytest.param("/base", ("/etc/passwd",), id="absolute"),
        pytest.param("/base", ("a", "/etc", "b"), id="later_absolute"),
        pytest.param("/base", ("../base2/x",), id="sibling_same_prefix"),
        pytest.param(".", ("../x",), id="relative_base_dot"),
        pytest.param("", ("../x",), id="relative_base_empty"),
        pytest.param("..", ("../x",), id="relative_base_parent"),
    ],
)
def test_safe_join_outside_base(base: str | Path, parts: tuple[str, ...]) -> None:
    """Test that safe_join raises an error for a path outside the base folder."""
    with pytest.raises(ValueError, match="outside the base folder"):
        safe_join(base, *parts)


@pytest.mark.parametrize(
    ("base", "parts"),
    [
        pytest.param("/base", ("a\0b",), id="part"),
        pytest.param("/base", ("bad\0/../x",), id="removed_by_normalization"),
        pytest.param("/ba\0se", ("x",), id="base"),
    ],
)
def test_safe_join_nul(base: str, parts: tuple[str, ...]) -> None:
    """Test that safe_join raises an error for a NUL character in the input."""
    with pytest.raises(ValueError, match="NUL character"):
        safe_join(base, *parts)
