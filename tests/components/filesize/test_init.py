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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmpdir: str
) -> None:
    """Test the Filesize configuration entry loading/unloading."""
    testfile = f"{tmpdir}/file.txt"
    create_file(testfile)
    hass.config.allowlist_external_dirs = {tmpdir}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=testfile, data={CONF_FILE_PATH: testfile}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_cannot_access_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmpdir: str
) -> None:
    """Test that an file not exist is caught."""
    mock_config_entry.add_to_hass(hass)
    testfile = f"{tmpdir}/file_not_exist.txt"
    hass.config.allowlist_external_dirs = {tmpdir}
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=testfile, data={CONF_FILE_PATH: testfile}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_not_valid_path_to_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmpdir: str
) -> None:
    """Test that an invalid path is caught."""
    testfile = f"{tmpdir}/file.txt"
    create_file(testfile)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=testfile, data={CONF_FILE_PATH: testfile}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
