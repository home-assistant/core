"""Tests for the Lunatone integration."""

import copy
from unittest.mock import AsyncMock

from lunatone_rest_api_client.models import LineStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.LIGHT)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on and off."""
    device_id = 1
    entity_id = f"light.device_{device_id}"

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        device = mock_lunatone_devices.data.devices[device_id - 1]
        device.features.switchable.status = not device.features.switchable.status

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_turn_on_off_with_brightness(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on with brightness."""
    device_id = 2
    entity_id = f"light.device_{device_id}"
    expected_brightness = 128
    brightness_percentages = iter([50.0, 0.0, 50.0])

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        brightness = next(brightness_percentages)
        device = mock_lunatone_devices.data.devices[device_id - 1]
        device.features.switchable.status = brightness > 0
        device.features.dimmable.status = brightness

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: expected_brightness},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == expected_brightness

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert not state.attributes["brightness"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == expected_brightness


async def test_turn_on_off_broadcast(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the broadcast light can be turned on and off."""
    entity_id = f"light.dali_line_{mock_lunatone_dali_broadcast.line}"

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 1
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 2
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 3
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()


async def test_line_broadcast_available_status(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the broadcast light is available."""
    entity_id = f"light.dali_line_{mock_lunatone_dali_broadcast.line}"

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        info_data = copy.deepcopy(mock_lunatone_info.data)
        info_data.lines["0"].line_status = LineStatus.NOT_REACHABLE
        mock_lunatone_info.data = info_data

    mock_lunatone_info.async_update.side_effect = fake_update

    state = hass.states.get(entity_id)
    assert state
    assert state.state != "unavailable"

    await mock_config_entry.runtime_data.coordinator_info.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_line_broadcast_line_present(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the broadcast light line is present."""
    mock_lunatone_dali_broadcast.line = None

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids("light")


@pytest.mark.parametrize(
    "color_temp_kelvin",
    [10000, 5000, 1000],
)
async def test_turn_on_with_color_temperature(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    color_temp_kelvin: int,
) -> None:
    """Test the color temperature of the light can be set."""
    device_id = 3
    entity_id = f"light.device_{device_id}"

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        device = mock_lunatone_devices.data.devices[device_id - 1]
        device.features.switchable.status = True
        device.features.color_kelvin.status = float(color_temp_kelvin)

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COLOR_TEMP_KELVIN: color_temp_kelvin,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == color_temp_kelvin


@pytest.mark.parametrize(
    "rgb_color",
    [(255, 128, 0), (0, 255, 128), (128, 0, 255)],
)
async def test_turn_on_with_rgb_color(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    rgb_color: tuple[int, int, int],
) -> None:
    """Test the RGB color of the light can be set."""
    device_id = 4
    entity_id = f"light.device_{device_id}"

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        device = mock_lunatone_devices.data.devices[device_id - 1]
        device.features.switchable.status = True
        device.features.color_rgb.status.red = rgb_color[0] / 255
        device.features.color_rgb.status.green = rgb_color[1] / 255
        device.features.color_rgb.status.blue = rgb_color[2] / 255

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: rgb_color,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_RGB_COLOR] == rgb_color


@pytest.mark.parametrize(
    "rgbw_color",
    [(255, 128, 0, 255), (0, 255, 128, 128), (128, 0, 255, 0)],
)
async def test_turn_on_with_rgbw_color(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    rgbw_color: tuple[int, int, int, int],
) -> None:
    """Test the RGBW color of the light can be set."""
    device_id = 5
    entity_id = f"light.device_{device_id}"

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        device = mock_lunatone_devices.data.devices[device_id - 1]
        device.features.switchable.status = True
        device.features.color_rgb.status.red = rgbw_color[0] / 255
        device.features.color_rgb.status.green = rgbw_color[1] / 255
        device.features.color_rgb.status.blue = rgbw_color[2] / 255
        device.features.color_waf.status.white = rgbw_color[3] / 255

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGBW_COLOR: rgbw_color,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_RGBW_COLOR] == rgbw_color
