"""The tests for the Tasmota binary sensor platform."""

import copy
import json
from unittest.mock import call

from homeassistant.components.tasmota.const import DEFAULT_PREFIX, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .test_common import DEFAULT_CONFIG, DEFAULT_SENSOR_CONFIG, remove_device

from tests.common import (
    MockConfigEntry,
    MockModule,
    async_fire_mqtt_message,
    mock_integration,
)
from tests.typing import MqttMockHAClient, WebSocketGenerator


async def test_device_remove(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a discovered device through device registry."""
    assert await async_setup_component(hass, "config", {})
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    async_fire_mqtt_message(
        hass, f"{DEFAULT_PREFIX}/{mac}/sensors", json.dumps(sensor_config)
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None

    await remove_device(hass, hass_ws_client, device_entry.id)
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_has_calls(
        [
            call(f"tasmota/discovery/{mac}/config", "", 0, True),
            call(f"tasmota/discovery/{mac}/sensors", "", 0, True),
        ],
        any_order=True,
    )


async def test_device_remove_non_tasmota_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test removing a non Tasmota device through device registry."""
    assert await async_setup_component(hass, "config", {})

    async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
    ) -> bool:
        return True

    mock_integration(
        hass,
        MockModule(
            "test", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.supports_remove_device = True
    config_entry.add_to_hass(hass)

    mac = "12:34:56:AB:CD:EF"
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )
    assert device_entry is not None

    await remove_device(hass, hass_ws_client, device_entry.id, config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None

    # Verify no Tasmota discovery message was sent
    mqtt_mock.async_publish.assert_not_called()


async def test_device_remove_stale_tasmota_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test removing a stale (undiscovered) Tasmota device through device registry."""
    assert await async_setup_component(hass, "config", {})
    config_entry = hass.config_entries.async_entries("tasmota")[0]

    mac = "12:34:56:AB:CD:EF"
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )
    assert device_entry is not None

    await remove_device(hass, hass_ws_client, device_entry.id)
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None

    # Verify retained discovery topic has not been cleared
    mqtt_mock.async_publish.assert_not_called()


async def test_tasmota_ws_remove_discovered_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test Tasmota websocket device removal."""
    assert await async_setup_component(hass, "config", {})
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None

    tasmota_config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await remove_device(
        hass, hass_ws_client, device_entry.id, tasmota_config_entry.entry_id
    )

    # Verify device entry is cleared
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None
