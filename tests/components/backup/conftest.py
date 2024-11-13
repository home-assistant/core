"""Test fixtures for the Backup integration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture(name="mocked_json_bytes")
def mocked_json_bytes_fixture() -> Generator[Mock]:
    """Mock json_bytes."""
    with patch(
        "homeassistant.components.backup.manager.json_bytes",
        return_value=b"{}",  # Empty JSON
    ) as mocked_json_bytes:
        yield mocked_json_bytes


@pytest.fixture(name="mocked_tarfile")
def mocked_tarfile_fixture() -> Generator[Mock]:
    """Mock tarfile."""
    with patch(
        "homeassistant.components.backup.manager.SecureTarFile"
    ) as mocked_tarfile:
        yield mocked_tarfile


@pytest.fixture(name="mock_backup_generation")
def mock_backup_generation_fixture(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> Generator[None]:
    """Mock backup generator."""

    def _mock_iterdir(path: Path) -> list[Path]:
        if not path.name.endswith("testing_config"):
            return []
        return [
            Path("test.txt"),
            Path(".DS_Store"),
            Path(".storage"),
        ]

    with (
        patch("pathlib.Path.iterdir", _mock_iterdir),
        patch("pathlib.Path.stat", MagicMock(st_size=123)),
        patch("pathlib.Path.is_file", lambda x: x.name != ".storage"),
        patch(
            "pathlib.Path.is_dir",
            lambda x: x.name == ".storage",
        ),
        patch(
            "pathlib.Path.exists",
            lambda x: x != Path(hass.config.path("backups")),
        ),
        patch(
            "pathlib.Path.is_symlink",
            lambda _: False,
        ),
        patch(
            "pathlib.Path.mkdir",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.backup.manager.HAVERSION",
            "2025.1.0",
        ),
    ):
        yield
