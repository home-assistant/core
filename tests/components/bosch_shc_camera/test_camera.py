"""Tests for camera.py's isolated (non-network) BoschCamera logic."""

from homeassistant.components.bosch_shc_camera.camera import _rotate_jpeg_180


def test_rotate_jpeg_180_returns_bytes_for_a_real_jpeg() -> None:
    """A valid JPEG is rotated and re-encoded, producing new (still JPEG) bytes."""
    # 1x1 black JPEG — same fixture BoschCamera._PLACEHOLDER_JPEG uses.
    placeholder = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff"
        b"\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r"
        b"\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' "
        b"\",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01"
        b"\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T"
        b"\xdf\xb2\x80\x01\xff\xd9"
    )
    rotated = _rotate_jpeg_180(placeholder)
    assert isinstance(rotated, bytes)
    assert rotated.startswith(b"\xff\xd8")  # still a valid JPEG (SOI marker)


def test_rotate_jpeg_180_returns_original_bytes_on_decode_failure() -> None:
    """Non-JPEG bytes fail to decode and the original bytes are returned unchanged."""
    garbage = b"not a jpeg at all"
    assert _rotate_jpeg_180(garbage) == garbage
