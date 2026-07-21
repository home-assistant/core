"""Tests for the Midea LAN integration."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from .conftest import DummyDevice

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, device: DummyDevice
) -> None:
    """Set up a Midea LAN config entry backed by a fake device."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=device,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
