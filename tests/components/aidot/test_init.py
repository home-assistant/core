"""Test aidot."""

from unittest.mock import MagicMock

from aidot.const import CONF_ACCESS_TOKEN, CONF_LOGIN_INFO

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.common import MockConfigEntry


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that async_unload_entry unloads the component correctly."""
    await async_init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_aidot_client: MagicMock,
) -> None:
    """Test setup fails with auth error."""
    from aidot.exceptions import AidotUserOrPassIncorrect

    mocked_aidot_client.async_post_login.side_effect = AidotUserOrPassIncorrect()
    # Remove access token to trigger login
    mock_config_entry.data[CONF_LOGIN_INFO].pop(CONF_ACCESS_TOKEN, None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
