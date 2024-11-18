"""Tests for JustNimbus initialization."""

from homeassistant.components.justnimbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FIXTURE_OLD_USER_INPUT, FIXTURE_UNIQUE_ID

from tests.common import MockConfigEntry


async def test_config_entry_reauth_at_setup(hass: HomeAssistant) -> None:
    """Test that setting up with old config results in reauth."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=FIXTURE_UNIQUE_ID, data=FIXTURE_OLD_USER_INPUT
    )
    mock_config.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

    assert mock_config.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config.async_get_active_flows(hass, {"reauth"}))
