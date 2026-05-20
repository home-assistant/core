"""UniFi Network binary sensor platform tests."""

from copy import deepcopy
from datetime import timedelta
from typing import Any

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from .conftest import WebsocketMessageMock

from tests.common import async_fire_time_changed

GATEWAY_WAN_DEVICE = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "UGW3",
    "name": "Gateway",
    "state": 1,
    "type": "ugw",
    "version": "4.4.44",
    "wan1": {
        "bytes-r": 242330,
        "enable": True,
        "full_duplex": True,
        "gateway": "2.3.4.5",
        "ifname": "eth0",
        "ip": "1.2.3.4",
        "mac": "00:00:00:00:01:01",
        "name": "wan",
        "netmask": "255.255.254.0",
        "rx_bytes-r": 239494,
        "speed": 1000,
        "tx_bytes-r": 2836,
        "type": "wire",
        "up": True,
        "latency": 5,
        "availability": 100.0,
    },
    "wan2": {
        "bytes-r": 1024,
        "enable": True,
        "full_duplex": True,
        "gateway": "10.0.0.1",
        "ifname": "eth1",
        "ip": "10.0.0.2",
        "mac": "00:00:00:00:01:02",
        "name": "wan2",
        "netmask": "255.255.255.0",
        "rx_bytes-r": 512,
        "speed": 1000,
        "tx_bytes-r": 512,
        "type": "wire",
        "up": True,
        "latency": 11,
        "availability": 99.5,
    },
    "last_wan_status": {
        "WAN": "online",
        "WAN2": "online",
    },
    "last_wan_ip": "1.2.3.4",
    "speedtest-status": {
        "latency": 12,
        "rundate": 1600000000,
        "runtime": 0,
        "status_download": 1,
        "status_ping": 1,
        "status_summary": 1,
        "status_upload": 1,
        "xput_download": 95.5,
        "xput_upload": 42.3,
    },
}


@pytest.mark.parametrize("device_payload", [[GATEWAY_WAN_DEVICE]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_wan_status_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that WAN status binary sensors are working as expected."""
    wan_entities = [
        "binary_sensor.gateway_wan_status",
        "binary_sensor.gateway_wan2_status",
    ]
    for entity_id in wan_entities:
        ent_reg_entry = entity_registry.async_get(entity_id)
        assert ent_reg_entry is not None, f"{entity_id} not found in registry"
        assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
        entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.gateway_wan_status").state == "on"
    assert hass.states.get("binary_sensor.gateway_wan2_status").state == "on"

    # WAN3-6 sensors should not exist (no data)
    assert entity_registry.async_get("binary_sensor.gateway_wan3_status") is None
    assert entity_registry.async_get("binary_sensor.gateway_wan4_status") is None
    assert entity_registry.async_get("binary_sensor.gateway_wan5_status") is None
    assert entity_registry.async_get("binary_sensor.gateway_wan6_status") is None

    # Simulate WAN1 going down
    device = deepcopy(GATEWAY_WAN_DEVICE)
    device["last_wan_status"]["WAN"] = "offline"
    mock_websocket_message(message=MessageKey.DEVICE, data=device)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.gateway_wan_status").state == "off"
    assert hass.states.get("binary_sensor.gateway_wan2_status").state == "on"
