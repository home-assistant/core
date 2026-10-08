"""Tests for the Shark IQ integration setup."""

from unittest.mock import patch

from homeassistant.components.sharkiq import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CONFIG, ENTRY_ID, UNIQUE_ID

from tests.common import MockConfigEntry


async def test_setup_authentication_failed(hass: HomeAssistant) -> None:
    """Test setup fails and starts reauth when authentication fails."""
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
    assert entry.reason == "Authentication error connecting to the Shark IQ API"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
