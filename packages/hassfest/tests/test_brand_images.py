"""Tests for hassfest brand_images."""

from pathlib import Path
import struct
import zlib

from hassfest import brand_images
from hassfest.model import Config, Integration
import pytest


def _png(width: int, height: int, content: bytes = b"") -> bytes:
    """Return a PNG header with the given size, followed by some content."""
    ihdr = b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        brand_images.PNG_SIGNATURE
        + struct.pack(">I", 13)
        + ihdr
        + struct.pack(">I", zlib.crc32(ihdr))
        + content
    )


def _validate(tmp_path: Path, config: Config, files: dict[str, bytes]) -> Integration:
    """Write a brand folder and validate it."""
    brand_dir = tmp_path / "test" / "brand"
    brand_dir.mkdir(parents=True)
    for name, data in files.items():
        (brand_dir / name).write_bytes(data)
    integration = Integration(
        tmp_path / "test",
        _config=config,
        _manifest={"domain": "test", "name": "Test"},
    )
    brand_images.validate({"test": integration}, config)
    return integration


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({"icon.png": _png(256, 256)}, id="icon_only"),
        pytest.param(
            {
                "icon.png": _png(256, 256),
                "icon@2x.png": _png(512, 512),
                "logo.png": _png(400, 128),
                "logo@2x.png": _png(800, 256),
                "dark_icon.png": _png(256, 256, b"dark"),
                "dark_logo.png": _png(400, 128, b"dark"),
            },
            id="full_set",
        ),
        pytest.param({"logo.png": _png(256, 600)}, id="tall_logo"),
        pytest.param(
            {
                "icon.png": _png(256, 256),
                "dark_icon.png": _png(256, 256, b"dark"),
                "dark_logo.png": _png(256, 256),
            },
            # dark_icon.png is served when dark_logo.png is missing, not icon.png.
            id="identical_to_later_fallback",
        ),
        pytest.param(
            {
                "icon.png": _png(256, 256),
                "dark_icon.png": _png(256, 256),
                "logo.png": _png(400, 128),
            },
            # Removing dark_icon.png would serve logo.png as the dark logo.
            id="duplicate_serves_other_fallback",
        ),
        pytest.param(
            {
                "icon.png": _png(256, 256),
                "dark_icon.png": _png(256, 256),
                "dark_icon@2x.png": _png(512, 512),
            },
            # dark_icon@2x.png requires dark_icon.png.
            id="duplicate_has_2x_companion",
        ),
    ],
)
def test_valid_brand_folder(
    tmp_path: Path, config: Config, files: dict[str, bytes]
) -> None:
    """Test valid brand folders."""
    integration = _validate(tmp_path, config, files)
    assert integration.errors == []
    assert integration.warnings == []


def test_no_brand_folder(tmp_path: Path, config: Config) -> None:
    """Test an integration without a brand folder."""
    (tmp_path / "test").mkdir()
    integration = Integration(
        tmp_path / "test",
        _config=config,
        _manifest={"domain": "test", "name": "Test"},
    )
    brand_images.validate({"test": integration}, config)
    assert integration.errors == []


@pytest.mark.parametrize(
    ("files", "error"),
    [
        pytest.param(
            {"icon.png": _png(512, 512)},
            "brand/icon.png is 512x512, but must be 256x256",
            id="icon_size",
        ),
        pytest.param(
            {"icon.png": _png(256, 256), "icon@2x.png": _png(256, 256, b"other")},
            "brand/icon@2x.png is 256x256, but must be 512x512",
            id="hdpi_icon_size",
        ),
        pytest.param(
            {"icon.png": _png(256, 256), "logo.png": _png(600, 100)},
            "brand/logo.png is 600x100, but its shortest side must be between 128"
            " and 256 pixels",
            id="logo_too_small",
        ),
        pytest.param(
            {"logo.png": _png(400, 128), "logo@2x.png": _png(1200, 600)},
            "brand/logo@2x.png is 1200x600, but its shortest side must be between 256"
            " and 512 pixels",
            id="hdpi_logo_too_large",
        ),
        pytest.param(
            {"icon@2x.png": _png(512, 512)},
            "brand/icon@2x.png is provided, but brand/icon.png is missing",
            id="hdpi_without_normal",
        ),
        pytest.param(
            {"icon.png": _png(256, 256), "dark_icon.png": _png(256, 256)},
            "brand/dark_icon.png is identical to brand/icon.png, which is used when"
            " brand/dark_icon.png is missing, remove brand/dark_icon.png",
            id="dark_identical_to_light",
        ),
        pytest.param(
            {"icon.png": _png(256, 256), "logo.png": _png(256, 256)},
            "brand/logo.png is identical to brand/icon.png, which is used when"
            " brand/logo.png is missing, remove brand/logo.png",
            id="logo_identical_to_icon",
        ),
        pytest.param(
            {"icon.png": b"<svg></svg>"},
            "brand/icon.png is not a PNG image",
            id="not_png",
        ),
        pytest.param(
            {"icon.png": _png(256, 256)[:18]},
            "brand/icon.png is not a PNG image",
            id="truncated_png",
        ),
        pytest.param(
            {"icon.png": _png(256, 256)[:24]},
            "brand/icon.png is not a PNG image",
            id="truncated_ihdr",
        ),
        pytest.param(
            {
                "icon.png": brand_images.PNG_SIGNATURE
                + struct.pack(">I", 12)
                + _png(256, 256)[12:]
            },
            "brand/icon.png is not a PNG image",
            id="malformed_ihdr_length",
        ),
        pytest.param(
            {"icon.png": _png(256, 256), "icon.svg": b"<svg></svg>"},
            "brand/icon.svg is not a brand image Home Assistant uses, allowed are:"
            " dark_icon.png, dark_icon@2x.png, dark_logo.png, dark_logo@2x.png,"
            " icon.png, icon@2x.png, logo.png, logo@2x.png",
            id="unknown_file",
        ),
    ],
)
def test_invalid_brand_folder(
    tmp_path: Path, config: Config, files: dict[str, bytes], error: str
) -> None:
    """Test invalid brand folders of custom integrations only warn."""
    integration = _validate(tmp_path, config, files)
    assert integration.errors == []
    assert [warning.error for warning in integration.warnings] == [error]


@pytest.mark.usefixtures("mock_core_integration")
def test_invalid_brand_folder_core(tmp_path: Path, config: Config) -> None:
    """Test invalid brand folders of core integrations are errors."""
    integration = _validate(tmp_path, config, {"icon.png": _png(512, 512)})
    assert integration.warnings == []
    assert [error.error for error in integration.errors] == [
        "brand/icon.png is 512x512, but must be 256x256"
    ]


def test_directory_in_brand_folder(tmp_path: Path, config: Config) -> None:
    """Test a directory in the brand folder is reported instead of read."""
    brand_dir = tmp_path / "test" / "brand"
    (brand_dir / "icon.png").mkdir(parents=True)
    (brand_dir / "logo.png").write_bytes(_png(400, 128))
    integration = Integration(
        tmp_path / "test",
        _config=config,
        _manifest={"domain": "test", "name": "Test"},
    )
    brand_images.validate({"test": integration}, config)
    assert integration.errors == []
    assert [warning.error for warning in integration.warnings] == [
        "brand/icon.png is not a file"
    ]
