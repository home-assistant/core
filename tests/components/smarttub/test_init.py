"""Test smarttub setup process."""

from smarttub import LoginFailed

from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_with_no_config(
    setup_component, hass: HomeAssistant, smarttub_api
) -> None:
    """Test that we do not discover anything."""

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    smarttub_api.login.assert_not_called()


async def test_setup_entry_not_ready(
    setup_component, hass: HomeAssistant, config_entry, smarttub_api
) -> None:
    """Test setup when the entry is not ready."""
    smarttub_api.login.side_effect = TimeoutError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(
    setup_component, hass: HomeAssistant, config_entry, smarttub_api
) -> None:
    """Test setup when the credentials are invalid."""
    smarttub_api.login.side_effect = LoginFailed

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_unload_entry(hass: HomeAssistant, config_entry) -> None:
    """Test being able to unload an entry."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
