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
    DOMAIN as FAN_DOMAIN,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_fan_entity_with_all_features_old_api(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic fan entity that uses the old api and has all features."""
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            unique_id="my_fan",
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
    state = hass.states.get("fan.test_myfan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.MEDIUM, state=True)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.LOW, state=True)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.HIGH, state=True)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, speed=FanSpeed.HIGH, state=True)]
    )
    mock_client.fan_command.reset_mock()


async def test_fan_entity_with_all_features_new_api(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic fan entity that uses the new api and has all features."""
    mock_client.api_version = APIVersion(1, 4)
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            unique_id="my_fan",
            supported_speed_levels=4,
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
            speed_level=3,
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
    state = hass.states.get("fan.test_myfan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, speed_level=1, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, speed_level=2, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, speed_level=2, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, speed_level=4, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, speed_level=4, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_OSCILLATING: True},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, oscillating=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_OSCILLATING: False},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, oscillating=False)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_DIRECTION: "forward"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.FORWARD)]
    )
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: "fan.test_myfan", ATTR_DIRECTION: "reverse"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls(
        [call(key=1, direction=FanDirection.REVERSE)]
    )
    mock_client.fan_command.reset_mock()


async def test_fan_entity_with_no_features_new_api(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic fan entity that uses the new api and has no features."""
    mock_client.api_version = APIVersion(1, 4)
    entity_info = [
        FanInfo(
            object_id="myfan",
            key=1,
            name="my fan",
            unique_id="my_fan",
            supports_direction=False,
            supports_speed=False,
            supports_oscillation=False,
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
    state = hass.states.get("fan.test_myfan")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=True)])
    mock_client.fan_command.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.test_myfan"},
        blocking=True,
    )
    mock_client.fan_command.assert_has_calls([call(key=1, state=False)])
    mock_client.fan_command.reset_mock()
