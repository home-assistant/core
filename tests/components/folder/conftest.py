"""Fixtures for Folder integration tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.folder.const import CONF_FILTER, CONF_FOLDER_PATHS, DOMAIN
from homeassistant.core import HomeAssistant

from . import TEST_FILE_CONTENT, TEST_FILE_NAME, TEST_FOLDER_NAME


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.folder.async_setup_entry", return_value=None):
        yield


@pytest.fixture
def folder_path(hass: HomeAssistant, tmp_path: Path) -> str:
    """Return an allowed folder containing one file."""
    folder = tmp_path / TEST_FOLDER_NAME
    folder.mkdir()
    (folder / TEST_FILE_NAME).write_text(TEST_FILE_CONTENT, encoding="utf8")
    hass.config.allowlist_external_dirs = {str(folder)}
    return str(folder)


@pytest.fixture
def mock_config_entry(folder_path: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=folder_path,
        options={CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*"},
        entry_id="01JD5CTQMH9FKEFQKZJ8MMBQ3X",
    )
