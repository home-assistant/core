"""Tests for the QR code component."""

from collections.abc import Generator
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.qrcode import decode_qr_image


@pytest.fixture(autouse=True)
def mock_pyzbar() -> Generator[MagicMock]:
    """Mock pyzbar module for environments without libzbar."""
    mock_zbar = MagicMock()
    mock_module = MagicMock()
    mock_module.pyzbar = mock_zbar
    with patch.dict(
        sys.modules,
        {
            "pyzbar": mock_module,
            "pyzbar.pyzbar": mock_zbar,
        },
    ):
        yield mock_zbar


def test_decode_qr_image_bytes(mock_pyzbar: MagicMock) -> None:
    """Test decoding QR code from image bytes."""
    mock_obj = MagicMock()
    mock_obj.data = b"https://example.com/qr"
    mock_pyzbar.decode.return_value = [mock_obj]

    with patch("homeassistant.components.qrcode.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_img
        results = decode_qr_image(b"fake_image_bytes")

    assert results == ["https://example.com/qr"]


def test_decode_qr_image_empty(mock_pyzbar: MagicMock) -> None:
    """Test decoding image with no QR code."""
    mock_pyzbar.decode.return_value = []

    with patch("homeassistant.components.qrcode.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_img
        results = decode_qr_image(b"fake_image_bytes")

    assert results == []


def test_decode_qr_image_non_utf8(mock_pyzbar: MagicMock) -> None:
    """Test decoding QR code with non-utf8 bytes."""
    mock_obj = MagicMock()
    mock_obj.data = b"abc\xff\xfe123"
    mock_pyzbar.decode.return_value = [mock_obj]

    with patch("homeassistant.components.qrcode.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_img
        results = decode_qr_image(b"fake_image_bytes")

    assert len(results) == 1
    assert "abc" in results[0]


def test_decode_qr_image_path(tmp_path: Path, mock_pyzbar: MagicMock) -> None:
    """Test decoding QR code from a file Path."""
    fake_file = tmp_path / "test_qr.png"
    fake_file.write_bytes(b"dummy")

    mock_obj = MagicMock()
    mock_obj.data = b"ssm://UI?k=test"
    mock_pyzbar.decode.return_value = [mock_obj]

    with patch("homeassistant.components.qrcode.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_img
        results = decode_qr_image(fake_file)

    assert results == ["ssm://UI?k=test"]
    mock_open.assert_called_once_with(fake_file)
