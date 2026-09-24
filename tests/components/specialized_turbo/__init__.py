"""Tests for the Specialized Turbo integration."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def setup_integration(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Set up the integration and inject one bike advertisement."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.bluetooth.manager.discovery_flow.async_create_flow"
    ):
        inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()
