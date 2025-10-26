"""Fixtures for Filesize integration tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.filesize.const import DOMAIN, PLATFORMS
from homeassistant.const import CONF_FILE_PATH, Platform

from . import TEST_FILE_NAME

from tests.common import MockConfigEntry


@pytest.fixture(name="load_platforms")
async def patch_platform_constant() -> list[Platform]:
    """Return list of platforms to load."""
    return PLATFORMS


@pytest.fixture
def mock_config_entry(
    tmp_path: Path, load_platforms: list[Platform]
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    return MockConfigEntry(
        title=TEST_FILE_NAME,
        domain=DOMAIN,
        entry_id="01JD5CTQMH9FKEFQKZJ8MMBQ3X",
        data={CONF_FILE_PATH: test_file},
        unique_id=test_file,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.filesize.async_setup_entry", return_value=True
    ):
        yield
