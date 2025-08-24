"""Test for airOS integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.airos.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG_V1 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
}


async def test_load_unload_entry(
    hass: HomeAssistant, mock_airos_client: MagicMock
) -> None:
    """Test setup and unload config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_V1,
        entry_id="1",
        unique_id="airos_device",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
