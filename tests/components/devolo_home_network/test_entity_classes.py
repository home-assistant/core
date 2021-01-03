"""Test the devolo Home Network entities."""
from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceUnavailable
from devolo_plc_api.plcnet_api.plcnetapi import PlcNetApi

from homeassistant.components.devolo_home_network.entity_classes import (
    DevoloNetworkOverviewEntity,
)
from homeassistant.core import HomeAssistant

from . import DISCOVERY_INFO, IP, PLCNET

from tests.async_mock import patch


async def test_network_overview_update(hass: HomeAssistant):
    """Test updating network overview."""
    with patch(
        "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        return_value=PLCNET,
    ):
        device = Device(ip=IP)
        device.plcnet = PlcNetApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = DevoloNetworkOverviewEntity(device, "test_device")
        await entity.async_update()
        assert entity.state == 1
        assert entity.available


async def test_network_overview_device_unavailable(hass: HomeAssistant):
    """Test failing update of the network overview."""
    with patch(
        "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        side_effect=DeviceUnavailable,
    ):
        device = Device(ip=IP)
        device.plcnet = PlcNetApi(ip=IP, session=None, info=DISCOVERY_INFO)
        entity = DevoloNetworkOverviewEntity(device, "test_device")
        await entity.async_update()
        assert not entity.available
