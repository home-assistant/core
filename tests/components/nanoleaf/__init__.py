"""Tests for the Nanoleaf integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_reauth_flows(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[ConfigFlowResult]:
    """Return the reauth flows in progress for the config entry."""
    return [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == SOURCE_REAUTH
        and flow["context"].get("entry_id") == config_entry.entry_id
    ]
