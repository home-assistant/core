"""The tests for the Tasmota camera platform."""

from asyncio import Future
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
from tests.typing import ClientSessionGenerator, MqttMockHAClient, MqttMockPahoClient

SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)


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


async def test_camera_single_frame(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test single frame capture."""

    class MockClientResponse:
        def __init__(self, text) -> None:
            self._text = text

        async def read(self):
            return self._text

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1

    mac = config["mac"]
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )

    mock_single_image_stream = Future()
    mock_single_image_stream.set_result(MockClientResponse(SMALLEST_VALID_JPEG_BYTES))

    with patch(
        "hatasmota.camera.TasmotaCamera.get_still_image_stream",
        return_value=mock_single_image_stream,
    ):
        client = await hass_client()
        resp = await client.get("/api/camera_proxy/camera.tasmota")
        await hass.async_block_till_done()

    assert resp.status == 200
    assert resp.content_type == "image/jpeg"
    assert resp.content_length == len(SMALLEST_VALID_JPEG_BYTES)
    assert await resp.read() == SMALLEST_VALID_JPEG_BYTES


async def test_camera_stream(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test mjpeg stream capture."""

    class MockClientResponse:
        def __init__(self, text) -> None:
            self._text = text
            self._frame_available = True

        async def read(self, buffer_size):
            if self._frame_available:
                self._frame_available = False
                return self._text
            return None

        def close(self):
            pass

        @property
        def headers(self):
            return {"Content-Type": "multipart/x-mixed-replace"}

        @property
        def content(self):
            return self

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["cam"] = 1

    mac = config["mac"]
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )

    mock_mjpeg_stream = Future()
    mock_mjpeg_stream.set_result(MockClientResponse(SMALLEST_VALID_JPEG_BYTES))

    with patch(
        "hatasmota.camera.TasmotaCamera.get_mjpeg_stream",
        return_value=mock_mjpeg_stream,
    ):
        client = await hass_client()
        resp = await client.get("/api/camera_proxy_stream/camera.tasmota")
        await hass.async_block_till_done()

    assert resp.status == 200
    assert resp.content_type == "multipart/x-mixed-replace"
    assert await resp.read() == SMALLEST_VALID_JPEG_BYTES
