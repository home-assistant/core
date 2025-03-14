"""Test the Dexcom config flow."""

from unittest.mock import patch

from pydexcom import AccountError, SessionError

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CONFIG, init_integration

from tests.common import MockConfigEntry


async def test_setup_entry_account_error(hass: HomeAssistant) -> None:
    """Test entry setup failed due to account error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data=CONFIG,
        options=None,
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom",
        side_effect=AccountError,
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_setup_entry_session_error(hass: HomeAssistant) -> None:
    """Test entry setup failed due to session error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data=CONFIG,
        options=None,
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom",
        side_effect=SessionError,
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
