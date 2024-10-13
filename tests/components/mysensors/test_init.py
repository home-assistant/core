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
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{config_entry.entry_id}-{node_id}")}
    )
    state = hass.states.get(entity_id)

    assert gateway.sensors
    assert gateway.sensors[node_id]
    assert device_entry
    assert state

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]
    await hass.async_block_till_done()

    assert node_id not in gateway.sensors
    assert gateway.tasks.persistence.need_save is True
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, f"{config_entry.entry_id}-1")}
    )
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)
