"""Testing the Prowl initialisation."""

from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_reload_unload_config_entry(
    hass: HomeAssistant,
    mock_pyprowl_config_entry: MockConfigEntry,
    mock_pyprowl_success,
) -> None:
    """Test the Prowl configuration entry loading/reloading/unloading."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyprowl_config_entry.state is ConfigEntryState.LOADED
    assert mock_pyprowl_success.verify_key.call_count > 0

    await hass.config_entries.async_reload(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_pyprowl_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_pyprowl_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_bad_api_key_config_entry(
    hass: HomeAssistant,
    mock_pyprowl_config_entry: MockConfigEntry,
    mock_pyprowl_forbidden,
) -> None:
    """Test the Prowl configuration entry dealing with bad API key."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyprowl_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_pyprowl_forbidden.verify_key.call_count > 0


async def test_api_timeout_config_entry(
    hass: HomeAssistant,
    mock_pyprowl_config_entry: MockConfigEntry,
    mock_pyprowl_timeout,
) -> None:
    """Test the Prowl configuration entry dealing with Timeout."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyprowl_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_pyprowl_timeout.verify_key.call_count > 0


async def test_config_entry_api_fail(
    hass: HomeAssistant, mock_pyprowl_config_entry: MockConfigEntry, mock_pyprowl_fail
) -> None:
    """Test the Prowl configuration entry dealing with API failures."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyprowl_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_pyprowl_fail.verify_key.call_count > 0
