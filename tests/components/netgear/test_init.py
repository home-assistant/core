"""Tests for the Netgear integration setup."""

from unittest.mock import Mock, patch

from pynetgear import Device

from homeassistant.components.netgear.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

SERIAL = "5ER1AL0000001"
HOST = "10.0.0.1"

ROUTER_INFOS = {
    "DeviceMode": "0",
    "ModelName": "RBR20",
    "SerialNumber": SERIAL,
    "Firmwareversion": "V2.3.5.26",
    "Hardwareversion": "N/A",
    "DeviceName": "Desk",
}

TRACKED_DEVICE = Device(
    name="Tracked-Device",
    ip="10.0.0.10",
    mac="AA:BB:CC:DD:EE:FF",
    type="wireless",
    signal=100,
    link_rate=800,
    allow_or_block="Allow",
    device_type=32,
    device_model="iPhone",
    ssid="MyWifi",
    conn_ap_mac="",
)


async def test_tracked_device_links_to_router(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a tracked device is linked to the router via its via_device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.netgear.router.Netgear") as netgear_mock:
        api = netgear_mock.return_value
        api.login_try_port = Mock(return_value=True)
        api.get_info = Mock(return_value=ROUTER_INFOS)
        api.port = 80
        api.ssl = False
        api.get_attached_devices_2 = Mock(return_value=[TRACKED_DEVICE])
        api.get_traffic_meter = Mock(return_value=None)
        api.get_new_speed_test_result = Mock(return_value=None)
        api.check_new_firmware = Mock(return_value=None)
        api.get_system_info = Mock(return_value=None)
        api.check_ethernet_link = Mock(return_value=None)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    router_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert router_device is not None

    tracked_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TRACKED_DEVICE.mac)), entry.entry_id
    )
    assert tracked_device is not None
    assert tracked_device.via_device_id == router_device.id


async def test_offline_device_keeps_stored_model(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a device restored while offline keeps its previously stored model.

    Offline devices are restored at startup with no model (router.py), which must not
    overwrite the model stored while the device was online.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.netgear.router.Netgear") as netgear_mock:
        api = netgear_mock.return_value
        api.login_try_port = Mock(return_value=True)
        api.get_info = Mock(return_value=ROUTER_INFOS)
        api.port = 80
        api.ssl = False
        api.get_attached_devices_2 = Mock(return_value=[TRACKED_DEVICE])
        api.get_traffic_meter = Mock(return_value=None)
        api.get_new_speed_test_result = Mock(return_value=None)
        api.check_new_firmware = Mock(return_value=None)
        api.get_system_info = Mock(return_value=None)
        api.check_ethernet_link = Mock(return_value=None)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        tracked_device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TRACKED_DEVICE.mac)),
            entry.entry_id,
        )
        assert tracked_device is not None
        assert tracked_device.model == TRACKED_DEVICE.device_model

        # Reload with the device offline; it is restored without a model.
        api.get_attached_devices_2 = Mock(return_value=[])
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    tracked_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TRACKED_DEVICE.mac)), entry.entry_id
    )
    assert tracked_device is not None
    assert tracked_device.model == TRACKED_DEVICE.device_model


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing an unexpected child device is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.netgear.router.Netgear") as netgear_mock:
        api = netgear_mock.return_value
        api.login_try_port = Mock(return_value=True)
        api.get_info = Mock(return_value=ROUTER_INFOS)
        api.port = 80
        api.ssl = False
        api.get_attached_devices_2 = Mock(return_value=[TRACKED_DEVICE])
        api.get_traffic_meter = Mock(return_value=None)
        api.get_new_speed_test_result = Mock(return_value=None)
        api.check_new_firmware = Mock(return_value=None)
        api.get_system_info = Mock(return_value=None)
        api.check_ethernet_link = Mock(return_value=None)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await async_setup_component(hass, "config", {})
    router_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test_child_device")},
        parent_device_id=router_device.id,
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(child_device.id)
    assert not response["success"]
    assert (
        response["error"]["message"]
        == "Failed to remove device entry, rejected by integration"
    )
    assert device_registry.async_get(child_device.id)
