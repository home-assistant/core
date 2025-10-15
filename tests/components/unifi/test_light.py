"""UniFi Network light platform tests."""

from copy import deepcopy
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

DEVICE_WITH_LED = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.0.1",
    "last_seen": 1562600145,
    "mac": "10:00:00:00:01:01",
    "model": "U6-Lite",
    "name": "Device with LED",
    "next_interval": 20,
    "state": 1,
    "type": "uap",
    "version": "4.0.42.10433",
    "led_override": "on",
    "led_override_color": "#0000ff",
    "led_override_color_brightness": 80,
    "hw_caps": 2,
}

DEVICE_WITHOUT_LED = {
    "board_rev": 2,
    "device_id": "mock-id-2",
    "ip": "10.0.0.2",
    "last_seen": 1562600145,
    "mac": "10:00:00:00:01:02",
    "model": "US-8-60W",
    "name": "Device without LED",
    "next_interval": 20,
    "state": 1,
    "type": "usw",
    "version": "4.0.42.10433",
    "hw_caps": 0,
}

DEVICE_LED_OFF = {
    "board_rev": 3,
    "device_id": "mock-id-3",
    "ip": "10.0.0.3",
    "last_seen": 1562600145,
    "mac": "10:00:00:00:01:03",
    "model": "U6-Pro",
    "name": "Device LED Off",
    "next_interval": 20,
    "state": 1,
    "type": "uap",
    "version": "4.0.42.10433",
    "led_override": "off",
    "led_override_color": "#ffffff",
    "led_override_color_brightness": 0,
    "hw_caps": 2,
}


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED, DEVICE_WITHOUT_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_lights(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test lights."""
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1

    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_ON
    assert light_entity.attributes["brightness"] == 204
    assert light_entity.attributes["rgb_color"] == (0, 0, 255)

    assert hass.states.get("light.device_without_led_led") is None


@pytest.mark.parametrize("device_payload", [[DEVICE_LED_OFF]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_off_state(
    hass: HomeAssistant,
) -> None:
    """Test light off state."""
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1

    light_entity = hass.states.get("light.device_led_off_led")
    assert light_entity is not None
    assert light_entity.state == STATE_OFF
    assert light_entity.attributes.get("brightness") is None
    assert light_entity.attributes.get("rgb_color") is None


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_turn_on_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test turn on and off."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/mock-id",
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.device_with_led_led"},
        blocking=True,
    )

    assert aioclient_mock.call_count == 1
    call_data = aioclient_mock.mock_calls[0][2]
    assert call_data["led_override"] == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.device_with_led_led"},
        blocking=True,
    )

    assert aioclient_mock.call_count == 2
    call_data = aioclient_mock.mock_calls[1][2]
    assert call_data["led_override"] == "on"


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_set_brightness(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test set brightness."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/mock-id",
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.device_with_led_led",
            ATTR_BRIGHTNESS: 127,
        },
        blocking=True,
    )

    assert aioclient_mock.call_count == 1
    call_data = aioclient_mock.mock_calls[0][2]
    assert call_data["led_override"] == "on"


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_set_rgb_color(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test set RGB color."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/mock-id",
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.device_with_led_led",
            ATTR_RGB_COLOR: (255, 0, 0),
        },
        blocking=True,
    )

    assert aioclient_mock.call_count == 1
    call_data = aioclient_mock.mock_calls[0][2]
    assert call_data["led_override"] == "on"


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_set_brightness_and_color(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test set brightness and color."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/mock-id",
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.device_with_led_led",
            ATTR_RGB_COLOR: (0, 255, 0),
            ATTR_BRIGHTNESS: 191,
        },
        blocking=True,
    )

    assert aioclient_mock.call_count == 1
    call_data = aioclient_mock.mock_calls[0][2]
    assert call_data["led_override"] == "on"


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_state_update_via_websocket(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test state update via websocket."""
    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_ON
    assert light_entity.attributes["rgb_color"] == (0, 0, 255)
    updated_device = deepcopy(DEVICE_WITH_LED)
    updated_device["led_override"] = "off"
    updated_device["led_override_color"] = "#ff0000"
    updated_device["led_override_color_brightness"] = 100

    mock_websocket_message(message=MessageKey.DEVICE, data=[updated_device])
    await hass.async_block_till_done()

    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_OFF
    assert light_entity.attributes.get("rgb_color") is None
    assert light_entity.attributes.get("brightness") is None


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_device_offline(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test device offline."""
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1
    assert hass.states.get("light.device_with_led_led") is not None

    offline_device = deepcopy(DEVICE_WITH_LED)
    offline_device["state"] = 0
    mock_websocket_message(message=MessageKey.DEVICE, data=[offline_device])
    await hass.async_block_till_done()

    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_ON


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_device_unavailable(
    hass: HomeAssistant,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Test device unavailable."""
    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_ON

    updated_device = deepcopy(DEVICE_WITH_LED)
    updated_device["state"] = 0

    await mock_websocket_state.disconnect()
    await hass.async_block_till_done()

    light_entity = hass.states.get("light.device_with_led_led")
    assert light_entity is not None
    assert light_entity.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_LED]])
async def test_light_platform_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform snapshot."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.LIGHT]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
