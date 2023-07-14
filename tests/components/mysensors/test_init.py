"""Test function in __init__.py."""
from __future__ import annotations

from mysensors import BaseSyncGateway
from mysensors.sensor import Sensor

from homeassistant.components.mysensors import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    gps_sensor: Sensor,
    integration: MockConfigEntry,
    gateway: BaseSyncGateway,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a device can be removed ok."""
    entity_id = "sensor.gps_sensor_1_1"
    node_id = 1
    config_entry = integration
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{config_entry.entry_id}-{node_id}")}
    )
    entity_registry = er.async_get(hass)
    state = hass.states.get(entity_id)

    assert gateway.sensors
    assert gateway.sensors[node_id]
    assert device_entry
    assert state

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()

    assert node_id not in gateway.sensors
    assert gateway.tasks.persistence.need_save is True
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, f"{config_entry.entry_id}-1")}
    )
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)
