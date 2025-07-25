"""The tests for the Tasmota camera platform."""

import copy
import json
from unittest.mock import patch

import pytest

from homeassistant.components.camera import CameraState
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, Platform
from homeassistant.core import HomeAssistant

from .test_common import (
    DEFAULT_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_deep_sleep_availability,
    help_test_deep_sleep_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient, MqttMockPahoClient


async def test_controlling_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.tasmota")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("camera.tasmota")
    assert state.state == CameraState.IDLE
    assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )


async def test_deep_sleep_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_deep_sleep_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )


async def test_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_availability(
        hass, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )


async def test_deep_sleep_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_deep_sleep_availability(
        hass, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )


async def test_availability_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_availability_discovery_update(
        hass, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )


async def test_availability_poll_state(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    poll_topic = "tasmota_49A3BC/cmnd/STATE"
    await help_test_availability_poll_state(
        hass, mqtt_client_mock, mqtt_mock, Platform.CAMERA, config, poll_topic, ""
    )


async def test_discovery_removal_camera(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removal of discovered camera."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["cam"] = 1
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["cam"] = 0

    await help_test_discovery_removal(
        hass,
        mqtt_mock,
        caplog,
        Platform.CAMERA,
        config1,
        config2,
        object_id="tasmota",
        name="Tasmota",
    )


async def test_discovery_update_unchanged_camera(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test update of discovered camera."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    with patch(
        "homeassistant.components.tasmota.camera.TasmotaCamera.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock,
            caplog,
            Platform.CAMERA,
            config,
            discovery_update,
            object_id="tasmota",
            name="Tasmota",
        )


async def test_discovery_device_remove(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    unique_id = f"{DEFAULT_CONFIG['mac']}_camera_camera_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, Platform.CAMERA, unique_id, config
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, Platform.CAMERA, config, object_id="tasmota"
    )
