"""Test ESPHome lights."""


from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    APIVersion,
    LightColorCapability,
    LightInfo,
    LightState,
)

from homeassistant.components.light import (
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MAX_MIREDS,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_MIN_MIREDS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_light_no_color_temp(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic light entity that does not support color temp."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[LightColorCapability.BRIGHTNESS],
        )
    ]
    states = [LightState(key=1, state=True, brightness=100)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_my_light")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_my_light"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=True, color_mode=LightColorCapability.BRIGHTNESS)]
    )
    mock_client.light_command.reset_mock()


async def test_light_color_temp(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic light entity that does supports color temp."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153.846161,
            max_mireds=370.370361,
            supported_color_modes=[
                LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
            ],
        )
    ]
    states = [
        LightState(
            key=1,
            state=True,
            brightness=100,
            color_temperature=153.846161,
            color_mode=LightColorCapability.COLOR_TEMPERATURE,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_my_light")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes

    assert attributes[ATTR_MIN_MIREDS] == 153
    assert attributes[ATTR_MAX_MIREDS] == 370

    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_my_light"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_my_light"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()


async def test_light_color_temp_legacy(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a legacy light entity that does supports color temp."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153.846161,
            max_mireds=370.370361,
            supported_color_modes=[
                LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
            ],
            legacy_supports_brightness=True,
            legacy_supports_color_temperature=True,
        )
    ]
    states = [
        LightState(
            key=1,
            state=True,
            brightness=100,
            red=1,
            green=1,
            blue=1,
            white=1,
            cold_white=1,
            color_temperature=153.846161,
            color_mode=19,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_my_light")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes

    assert attributes[ATTR_MIN_MIREDS] == 153
    assert attributes[ATTR_MAX_MIREDS] == 370

    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_my_light"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_my_light"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()
