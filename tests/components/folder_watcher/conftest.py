"""Fixtures for Folder Watcher integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import pytest

from homeassistant.components.folder_watcher.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import TEST_DIR, create_file, remove_test_file

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.folder_watcher.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
async def load_int(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    hass.config.allowlist_external_dirs = {TEST_DIR}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title=f"Folder Watcher {str(TEST_DIR)}",
        data={},
        options={"folder": str(TEST_DIR), "patterns": ["*"]},
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.folder_watcher.Watcher.shutdown",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(autouse=True)
async def cleanup(hass: HomeAssistant) -> AsyncGenerator[None, None]:
    """Cleanup the test folder."""
    await hass.async_add_executor_job(create_file)
    yield
    await hass.async_add_executor_job(remove_test_file)
