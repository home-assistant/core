"""Test Home Assistant file utility functions."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.util.file import WriteError, write_utf8_file, write_utf8_file_atomic


@pytest.mark.parametrize("func", [write_utf8_file, write_utf8_file_atomic])
def test_write_utf8_file_atomic_private(tmp_path: Path, func) -> None:
    """Test files can be written as 0o600 or 0o644."""
    test_file = tmp_path / "test.json"

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


def test_write_utf8_file_fails_at_creation(tmp_path: Path) -> None:
    """Test that failed creation of the temp file does not create an empty file."""
    test_file = tmp_path / "test.json"

    with (
        pytest.raises(WriteError),
        patch(
            "homeassistant.util.file.tempfile.NamedTemporaryFile", side_effect=OSError
        ),
    ):
        write_utf8_file(test_file, '{"some":"data"}', False)

    assert not test_file.exists()


def test_write_utf8_file_fails_at_rename(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that if rename fails not not remove, we do not log the failed cleanup."""
    test_file = tmp_path / "test.json"

    with (
        pytest.raises(WriteError),
        patch("homeassistant.util.file.os.replace", side_effect=OSError),
    ):
        write_utf8_file(test_file, '{"some":"data"}', False)

    assert not test_file.exists()

    assert "File replacement cleanup failed" not in caplog.text


def test_write_utf8_file_fails_at_rename_and_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that if rename and remove both fail, we log the failed cleanup."""
    test_file = tmp_path / "test.json"

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

    with open(test_file, encoding="utf-8") as fh:
        assert fh.read() == non_ascii_data


def test_write_utf8_file_atomic_fails(tmp_path: Path) -> None:
    """Test OSError from write_utf8_file_atomic is rethrown as WriteError."""
    test_file = tmp_path / "test.json"

    with (
        pytest.raises(WriteError),
        patch("homeassistant.util.file.AtomicWriter.open", side_effect=OSError),
    ):
        write_utf8_file_atomic(test_file, '{"some":"data"}', False)

    assert not test_file.exists()
