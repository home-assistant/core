"""Configure pytest for downloader tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.downloader.const import CONF_DOWNLOAD_DIR, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def loaded_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up loaded config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DOWNLOAD_DIR: "/test_dir",
        },
    )
    config_entry.add_to_hass(hass)

    with patch("os.path.isdir", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry
