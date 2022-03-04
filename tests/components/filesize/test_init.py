"""Tests for the Filesize integration."""
from unittest.mock import AsyncMock

from homeassistant.components.filesize.const import CONF_FILE_PATHS, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    TEST_DIR,
    TEST_FILE,
    TEST_FILE2,
    TEST_FILE_NAME,
    TEST_FILE_NAME2,
    create_file,
)

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Filesize configuration entry loading/unloading."""
    create_file(TEST_FILE)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_import_config(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Filesize being set up from config via import."""
    create_file(TEST_FILE)
    create_file(TEST_FILE2)
    hass.config.allowlist_external_dirs = {TEST_DIR}
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                CONF_FILE_PATHS: [TEST_FILE, TEST_FILE2],
            }
        },
    )
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 2

    entry = config_entries[0]
    assert entry.title == TEST_FILE_NAME
    assert entry.unique_id == TEST_FILE
    assert entry.data == {CONF_FILE_PATH: TEST_FILE}
    entry2 = config_entries[1]
    assert entry2.title == TEST_FILE_NAME2
    assert entry2.unique_id == TEST_FILE2
    assert entry2.data == {CONF_FILE_PATH: TEST_FILE2}
