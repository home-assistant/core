"""Tests for Easywave gateway device registry helpers."""

from homeassistant.components.easywave.const import DOMAIN
from homeassistant.components.easywave.gateway_device import update_gateway_device
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_ENTRY_DATA

from tests.common import MockConfigEntry


async def test_update_gateway_device_registers_versions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway device registry entry includes hardware and firmware versions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    transceiver = type(
        "Transceiver",
        (),
        {
            "usb_serial_number": "67890",
            "hw_version": "RX11 v1.0",
            "fw_version": "FW 2.3.4",
        },
    )()

    update_gateway_device(hass, entry, transceiver)

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.hw_version == "RX11 v1.0"
    assert device.sw_version == "FW 2.3.4"
    assert device.serial_number == "67890"


async def test_update_gateway_device_updates_existing_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Reconnecting updates previously missing gateway versions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="RX11 USB Transceiver",
        manufacturer="ELDAT",
        model="RX11 USB Transceiver",
    )

    transceiver = type(
        "Transceiver",
        (),
        {
            "usb_serial_number": "67890",
            "hw_version": "RX11 v1.0",
            "fw_version": "FW 2.3.4",
        },
    )()

    update_gateway_device(hass, entry, transceiver)

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.hw_version == "RX11 v1.0"
    assert device.sw_version == "FW 2.3.4"
