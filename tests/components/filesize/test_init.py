"""Tests for the Filesize integration."""
from homeassistant.components.filesize.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant

from . import async_create_file

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmpdir: str
) -> None:
    """Test the Filesize configuration entry loading/unloading."""
    testfile = f"{tmpdir}/file.txt"
    await async_create_file(hass, testfile)
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
    await async_create_file(hass, testfile)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=testfile, data={CONF_FILE_PATH: testfile}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
