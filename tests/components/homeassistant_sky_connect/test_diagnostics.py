"""Tests for the Home Assistant SkyConnect diagnostics data."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import USB_DATA_ZBT1


async def test_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    await async_setup_component(hass, "homeassistant", {})

    zha_config_entry = MockConfigEntry(domain="zha")
    zha_config_entry.add_to_hass(hass)

    config_entry = MockConfigEntry(
        domain="homeassistant_sky_connect",
        unique_id=USB_DATA_ZBT1.serial_number,
        data={
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0 build 0",
            "device": USB_DATA_ZBT1.device,
            "manufacturer": USB_DATA_ZBT1.manufacturer,
            "pid": USB_DATA_ZBT1.pid,
            "product": USB_DATA_ZBT1.description,
            "serial_number": USB_DATA_ZBT1.serial_number,
            "vid": USB_DATA_ZBT1.vid,
        },
        version=1,
        minor_version=5,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.homeassistant_sky_connect.diagnostics.guess_hardware_owners",
        return_value=[
            FirmwareInfo(
                device=USB_DATA_ZBT1.device,
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0 build 0",
                source="zha",
                owners=[OwningIntegration(config_entry_id=zha_config_entry.entry_id)],
            ),
            FirmwareInfo(
                device=USB_DATA_ZBT1.device,
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="zigbee2mqtt (core_zigbee2mqtt)",
                owners=[OwningAddon(slug="core_zigbee2mqtt")],
            ),
        ],
    ):
        diagnostics_data = await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        )

    assert diagnostics_data == snapshot
