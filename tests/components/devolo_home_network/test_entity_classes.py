"""Test the devolo Home Network entities."""
from devolo_plc_api.device import Device
from devolo_plc_api.device_api.deviceapi import DeviceApi
from devolo_plc_api.exceptions.device import DeviceUnavailable
from devolo_plc_api.plcnet_api.plcnetapi import PlcNetApi
import pytest

from homeassistant.components.devolo_home_network.entity_classes import (
    DevoloNetworkOverviewEntity,
    DevoloWifiClientsEntity,
    DevoloWifiNetworksEntity,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONNECTED_STATIONS,
    DISCOVERY_INFO,
    IP,
    NEIGHBOR_ACCESS_POINTS,
    PLCNET,
)

from tests.async_mock import AsyncMock, patch


async def test_network_overview_update(hass: HomeAssistant):
    """Test updating network overview."""
    with patch(
        "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        new=AsyncMock(return_value=PLCNET),
    ):
        device = Device(ip=IP)
        device.plcnet = PlcNetApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = DevoloNetworkOverviewEntity(device, "test_device")
        await entity.async_update()
        assert entity.state == 1
        assert entity.available


async def test_wifi_connected_stations_update(hass: HomeAssistant):
    """Test updating network overview."""
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        new=AsyncMock(return_value=CONNECTED_STATIONS),
    ):
        device = Device(ip=IP)
        device.device = DeviceApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = DevoloWifiClientsEntity(device, "test_device")
        await entity.async_update()
        assert entity.state == 1
        assert entity.available


async def test_wifi_wifi_neighbor_access_points_update(hass: HomeAssistant):
    """Test updating network overview."""
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
        new=AsyncMock(return_value=NEIGHBOR_ACCESS_POINTS),
    ):
        device = Device(ip=IP)
        device.device = DeviceApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = DevoloWifiNetworksEntity(device, "test_device")
        await entity.async_update()
        assert entity.state == 1
        assert entity.available


@pytest.mark.parametrize(
    "entities",
    [DevoloNetworkOverviewEntity, DevoloWifiClientsEntity, DevoloWifiNetworksEntity],
)
async def test_deviceapi_unavailable(hass: HomeAssistant, entities):
    """Test failing updates of the DeviceApi."""
    getter = {
        DevoloNetworkOverviewEntity: "plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        DevoloWifiClientsEntity: "device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        DevoloWifiNetworksEntity: "device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
    }
    with patch(
        f"devolo_plc_api.{getter[entities]}",
        side_effect=DeviceUnavailable,
    ):
        device = Device(ip=IP)
        device.device = DeviceApi(ip=IP, session=None, info=DISCOVERY_INFO)
        device.plcnet = PlcNetApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = entities(device, "test_device")
        await entity.async_update()
        assert not entity.available
