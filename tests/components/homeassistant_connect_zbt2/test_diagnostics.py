"""Tests for the Home Assistant Connect ZBT-2 diagnostics data."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import USB_DATA_ZBT2

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    await async_setup_component(hass, "homeassistant", {})

    # Set up the ZBT-2 integration
    zbt2_config_entry = MockConfigEntry(
        domain="homeassistant_connect_zbt2",
        data={
            "firmware": "ezsp",
            "firmware_version": "7.3.1.0 build 0",
            "device": USB_DATA_ZBT2.device,
            "manufacturer": USB_DATA_ZBT2.manufacturer,
            "pid": USB_DATA_ZBT2.pid,
            "product": USB_DATA_ZBT2.description,
            "serial_number": USB_DATA_ZBT2.serial_number,
            "vid": USB_DATA_ZBT2.vid,
        },
        version=1,
        minor_version=1,
    )
    zbt2_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(zbt2_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, zbt2_config_entry
    )

    assert diagnostics_data == snapshot(
        exclude=props("created_at", "modified_at", "entry_id")
    )
