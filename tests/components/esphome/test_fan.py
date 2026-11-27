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
    DOMAIN as FAN_DOMAIN,
    STATE_ON,
    FanService,
    FanServiceArgument,
)
from homeassistant.const import TargetKey
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
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.MEDIUM, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.DECREASE_SPEED,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.INCREASE_SPEED,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.HIGH, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_OFF,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PERCENTAGE,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 100},
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
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=1, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=2, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.DECREASE_SPEED,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=2, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.INCREASE_SPEED,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=4, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_OFF,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PERCENTAGE,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 100},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed_level=4, state=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PERCENTAGE,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.PERCENTAGE: 0},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.OSCILLATE,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.OSCILLATING: True},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, oscillating=True, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.OSCILLATE,
        {TargetKey.ENTITY_ID: "fan.test_my_fan", FanServiceArgument.OSCILLATING: False},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, oscillating=False, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_DIRECTION,
        {
            TargetKey.ENTITY_ID: "fan.test_my_fan",
            FanServiceArgument.DIRECTION: "forward",
        },
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.FORWARD, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_DIRECTION,
        {
            TargetKey.ENTITY_ID: "fan.test_my_fan",
            FanServiceArgument.DIRECTION: "reverse",
        },
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.REVERSE, device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: "fan.test_my_fan",
            FanServiceArgument.PRESET_MODE: "Preset1",
        },
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, preset_mode="Preset1", device_id=0)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_ON,
        {
            TargetKey.ENTITY_ID: "fan.test_my_fan",
            FanServiceArgument.PRESET_MODE: "Preset2",
        },
        blocking=True,
    )
    mock_client.fan_command.assert_called_once_with(
        key=1, state=True, preset_mode="Preset2", device_id=0
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
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=True, device_id=0)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_OFF,
        {TargetKey.ENTITY_ID: "fan.test_my_fan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False, device_id=0)])
    mock_client.fan_command.reset_mock()
