"""The tests for the PG LAB Electronics  discovery device."""

import json

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_device_discover(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
) -> None:
    """Test setting up a device."""
    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "11000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None
    assert device_entry.configuration_url == f"http://{payload['ip']}/"
    assert device_entry.manufacturer == "PG LAB Electronics"
    assert device_entry.model == payload["type"]
    assert device_entry.name == payload["name"]
    assert device_entry.sw_version == payload["fw"]


async def test_device_update(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
    snapshot: SnapshotAssertion,
) -> None:
    """Test update a device."""
    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "11000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None

    # update device
    payload["fw"] = "1.0.1"
    payload["hw"] = "1.0.8"

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "1.0.1"
    assert device_entry.hw_version == "1.0.8"


async def test_device_remove(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
) -> None:
    """Test remove a device."""
    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "11000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None

    async_fire_mqtt_message(
        hass,
        topic,
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is None
