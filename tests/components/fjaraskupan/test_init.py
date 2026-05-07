"""Test the Fjäråskupan integration init."""

from fjaraskupan import ANNOUNCE_MANUFACTURER, DEVICE_NAME
from habluetooth import BluetoothServiceInfo

from homeassistant.components.fjaraskupan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_discovered_devices,
)
from tests.typing import WebSocketGenerator

MOCK_SERVICE_INFO = BluetoothServiceInfo(
    address="11:11:11:11:11:11",
    name=DEVICE_NAME,
    service_uuids=[],
    rssi=-60,
    manufacturer_data={ANNOUNCE_MANUFACTURER: b"ODFJAR\x01\x02\x00\x00\x00\x30\x04"},
    service_data={},
    source="local",
)


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup creates expected device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is True

    inject_bluetooth_service_info(
        hass,
        MOCK_SERVICE_INFO,
    )

    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERVICE_INFO.address)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "Fjäråskupan"
    assert device_entry.name == "Fjäråskupan"


async def test_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can remove devices that are not available."""
    assert await async_setup_component(hass, "config", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is True

    inject_bluetooth_service_info(hass, MOCK_SERVICE_INFO)

    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERVICE_INFO.address)}
    )
    assert device_entry

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert not response["success"]

    await hass.async_block_till_done()
    assert device_registry.async_get(device_entry.id)

    with patch_discovered_devices([]):
        response = await client.remove_device(device_entry.id, config_entry.entry_id)
        assert response["success"]

        await hass.async_block_till_done()
        assert not device_registry.async_get(device_entry.id)
