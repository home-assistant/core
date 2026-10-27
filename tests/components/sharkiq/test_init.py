"""Tests for the Shark IQ integration setup."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sharkiq import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CONFIG, ENTRY_ID, UNIQUE_ID


async def test_setup_sign_in_failed(hass: HomeAssistant) -> None:
    """Test setup fails without starting reauth when signing in fails."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG, entry_id=ENTRY_ID
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sharkiq.async_connect_or_timeout",
        return_value=False,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Error signing in to the Shark IQ API"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
