"""Test ESPHome fans."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    APIVersion,
    FanDirection,
    FanInfo,
    FanSpeed,
    FanState,
)

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_fan_entity_with_all_features_old_api(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic fan entity that uses the old api and has all features."""
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            supports_direction=True,
            supports_speed=True,
            supports_oscillation=True,
        )
    ]
    states = [
        FanState(
            key=1,
            state=True,
            oscillating=True,
            speed=FanSpeed.MEDIUM,
            direction=FanDirection.REVERSE,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("fan.test_my_fan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.MEDIUM, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.HIGH, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.HIGH, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()


async def test_fan_entity_with_all_features_new_api(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic fan entity that uses the new api and has all features."""
    mock_client.api_version = APIVersion(1, 4)
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            supported_speed_count=4,
            supports_direction=True,
            supports_speed=True,
            supports_oscillation=True,
            supported_preset_modes=["Preset1", "Preset2"],
        )
    ]
    states = [
        FanState(
            key=1,
            state=True,
            oscillating=True,
            speed_level=3,
            direction=FanDirection.REVERSE,
            preset_mode=None,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("fan.test_my_fan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=1, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=2, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=2, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=4, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=4, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_OSCILLATING: True},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, oscillating=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_OSCILLATING: False},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, oscillating=False, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_DIRECTION: "forward"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.FORWARD, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_DIRECTION: "reverse"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.REVERSE, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.test_my_fan", ATTR_PRESET_MODE: "Preset1"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, preset_mode="Preset1", device_id=0)]
    )
    mock_client.fan_command.reset_mock()


async def test_fan_entity_with_no_features_new_api(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic fan entity that uses the new api and has no features."""
    mock_client.api_version = APIVersion(1, 4)
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            supports_direction=False,
            supports_speed=False,
            supports_oscillation=False,
            supported_preset_modes=[],
        )
    ]
    states = [FanState(key=1, state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("fan.test_my_fan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=True, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()
