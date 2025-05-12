"""Test ESPHome lights."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    APIVersion,
    ColorMode as ESPColorMode,
    LightColorCapability,
    LightInfo,
    LightState,
)
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    FLASH_LONG,
    FLASH_SHORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType

LIGHT_COLOR_CAPABILITY_UNKNOWN = 1 << 8  # 256


async def test_light_on_off(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that only supports on/off."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[ESPColorMode.ON_OFF],
        )
    ]
    states = [LightState(key=1, state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=True, color_mode=LightColorCapability.ON_OFF)]
    )
    mock_client.light_command.reset_mock()


async def test_light_brightness(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that only supports brightness."""
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=True, color_mode=LightColorCapability.BRIGHTNESS)]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_TRANSITION: 2},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=False, transition_length=2.0)]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_FLASH: FLASH_LONG},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=False, flash_length=10.0)]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_TRANSITION: 2},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                transition_length=2.0,
                color_mode=LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_FLASH: FLASH_SHORT},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                flash_length=2.0,
                color_mode=LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_brightness_on_off(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that only supports brightness."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[ESPColorMode.ON_OFF, ESPColorMode.BRIGHTNESS],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.BRIGHTNESS,
    ]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_legacy_white_converted_to_brightness(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that only supports legacy white."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[
                LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LightColorCapability.WHITE
            ],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LightColorCapability.WHITE,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_legacy_white_with_rgb(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity with rgb and white."""
    mock_client.api_version = APIVersion(1, 7)
    color_mode = (
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.WHITE
    )
    color_mode_2 = (
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB
    )
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[color_mode, color_mode_2],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.RGB,
        ColorMode.WHITE,
    ]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_WHITE: 60},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                brightness=pytest.approx(0.23529411764705882),
                white=1.0,
                color_mode=color_mode,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_brightness_on_off_with_unknown_color_mode(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that only supports brightness along with an unknown color mode."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[
                LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LIGHT_COLOR_CAPABILITY_UNKNOWN
            ],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LIGHT_COLOR_CAPABILITY_UNKNOWN,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LIGHT_COLOR_CAPABILITY_UNKNOWN,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_on_and_brightness(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that supports on and on and brightness."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[
                LightColorCapability.ON_OFF | LightColorCapability.BRIGHTNESS,
                LightColorCapability.ON_OFF,
            ],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=True, color_mode=LightColorCapability.ON_OFF)]
    )
    mock_client.light_command.reset_mock()


async def test_rgb_color_temp_light(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light that supports color temp and RGB."""
    color_modes = [
        LightColorCapability.ON_OFF | LightColorCapability.BRIGHTNESS,
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.COLOR_TEMPERATURE,
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB,
    ]

    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=color_modes,
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_COLOR_TEMP_KELVIN: 2500},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
                | LightColorCapability.COLOR_TEMPERATURE,
                color_temperature=400,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_rgb(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic RGB light entity."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            supported_color_modes=[
                LightColorCapability.RGB
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
            ],
        )
    ]
    states = [LightState(key=1, state=True, brightness=100, red=1, green=1, blue=1)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_BRIGHTNESS: 127,
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(pytest.approx(0.3333333333333333), 1.0, 0.0),
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(1, 1, 1),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_rgbw(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic RGBW light entity."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            supported_color_modes=[
                LightColorCapability.RGB
                | LightColorCapability.WHITE
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
            red=1,
            green=1,
            blue=1,
            white=1,
            color_mode=LightColorCapability.RGB
            | LightColorCapability.WHITE
            | LightColorCapability.ON_OFF
            | LightColorCapability.BRIGHTNESS,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBW]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBW

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_BRIGHTNESS: 127,
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                white=0,
                rgb=(pytest.approx(0.3333333333333333), 1.0, 0.0),
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=0.0,
                white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, 0, 0),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(1, 1, 1),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_rgbww_with_cold_warm_white_support(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic RGBWW light entity with cold warm white support."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[
                LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
            ],
        )
    ]
    states = [
        LightState(
            key=1,
            state=True,
            color_brightness=1,
            brightness=100,
            red=1,
            green=1,
            blue=1,
            warm_white=1,
            cold_white=1,
            color_mode=LightColorCapability.RGB
            | LightColorCapability.WHITE
            | LightColorCapability.COLOR_TEMPERATURE
            | LightColorCapability.COLD_WARM_WHITE
            | LightColorCapability.ON_OFF
            | LightColorCapability.BRIGHTNESS,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBWW]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBWW
    assert state.attributes[ATTR_RGBWW_COLOR] == (255, 255, 255, 255, 255)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_BRIGHTNESS: 127,
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                cold_white=0,
                warm_white=0,
                rgb=(pytest.approx(0.3333333333333333), 1.0, 0.0),
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=pytest.approx(0.4235294117647059),
                cold_white=1,
                warm_white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, pytest.approx(0.5462962962962963), 1.0),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=pytest.approx(0.4235294117647059),
                cold_white=1,
                warm_white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, pytest.approx(0.5462962962962963), 1.0),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_RGBWW_COLOR: (255, 255, 255, 255, 255),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1,
                cold_white=1,
                warm_white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(1, 1, 1),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_COLOR_TEMP_KELVIN: 2500},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=0,
                cold_white=0,
                warm_white=100,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.COLD_WARM_WHITE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, 0, 0),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_rgbww_without_cold_warm_white_support(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic RGBWW light entity without cold warm white support."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[
                LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS
            ],
        )
    ]
    states = [
        LightState(
            key=1,
            state=True,
            color_brightness=1,
            brightness=100,
            red=1,
            green=1,
            blue=1,
            white=1,
            color_mode=LightColorCapability.RGB
            | LightColorCapability.WHITE
            | LightColorCapability.COLOR_TEMPERATURE
            | LightColorCapability.ON_OFF
            | LightColorCapability.BRIGHTNESS,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBWW]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBWW
    assert state.attributes[ATTR_RGBWW_COLOR] == (255, 255, 255, 255, 0)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_BRIGHTNESS: 127,
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                white=0,
                rgb=(pytest.approx(0.3333333333333333), 1.0, 0.0),
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )

    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=pytest.approx(0.4235294117647059),
                color_temperature=276.5,
                white=1,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, pytest.approx(0.5462962962962963), 1.0),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=pytest.approx(0.4235294117647059),
                white=1,
                color_temperature=276.5,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, pytest.approx(0.5462962962962963), 1.0),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_mylight",
            ATTR_RGBWW_COLOR: (255, 255, 255, 255, 255),
        },
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=1,
                white=1,
                color_temperature=276.5,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(1, 1, 1),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_COLOR_TEMP_KELVIN: 2500},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_brightness=0,
                white=100,
                color_temperature=400.0,
                color_mode=LightColorCapability.RGB
                | LightColorCapability.WHITE
                | LightColorCapability.COLOR_TEMPERATURE
                | LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                rgb=(0, 0, 0),
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_color_temp(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes

    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
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
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()


async def test_light_color_temp_no_mireds_set(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic color temp with no mireds set uses the defaults."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=0,
            max_mireds=0,
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes

    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 0
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
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
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_COLOR_TEMP_KELVIN: 6000},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_temperature=pytest.approx(166.66666666666666),
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
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()


async def test_light_color_temp_legacy(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes

    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]

    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
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
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()


async def test_light_rgb_legacy(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a legacy light entity that supports rgb."""
    mock_client.api_version = APIVersion(1, 5)
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
                | LightColorCapability.RGB
            ],
            legacy_supports_brightness=True,
            legacy_supports_color_temperature=True,
            legacy_supports_rgb=True,
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
            color_mode=LightColorCapability.COLOR_TEMPERATURE
            | LightColorCapability.ON_OFF
            | LightColorCapability.BRIGHTNESS
            | LightColorCapability.RGB,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGB

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=False)])
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_RGB_COLOR: (255, 255, 255)},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                rgb=(1.0, 1.0, 1.0),
                color_brightness=1.0,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_effects(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity that supports on and on and brightness."""
    mock_client.api_version = APIVersion(1, 7)
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            effects=["effect1", "effect2"],
            supported_color_modes=[
                LightColorCapability.ON_OFF | LightColorCapability.BRIGHTNESS,
            ],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT_LIST] == ["effect1", "effect2"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_EFFECT: "effect1"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=LightColorCapability.ON_OFF
                | LightColorCapability.BRIGHTNESS,
                effect="effect1",
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_only_cold_warm_white_support(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity with only cold warm white support."""
    mock_client.api_version = APIVersion(1, 7)
    color_modes = (
        LightColorCapability.COLD_WARM_WHITE
        | LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
    )
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[color_modes],
        )
    ]
    states = [
        LightState(
            key=1,
            state=True,
            color_brightness=1,
            brightness=100,
            red=1,
            green=1,
            blue=1,
            warm_white=1,
            cold_white=1,
            color_mode=color_modes,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [call(key=1, state=True, color_mode=color_modes)]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_BRIGHTNESS: 127},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=color_modes,
                brightness=pytest.approx(0.4980392156862745),
            )
        ]
    )
    mock_client.light_command.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight", ATTR_COLOR_TEMP_KELVIN: 2500},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls(
        [
            call(
                key=1,
                state=True,
                color_mode=color_modes,
                color_temperature=400.0,
            )
        ]
    )
    mock_client.light_command.reset_mock()


async def test_light_no_color_modes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic light entity with no color modes."""
    mock_client.api_version = APIVersion(1, 7)
    color_mode = 0
    entity_info = [
        LightInfo(
            object_id="mylight",
            key=1,
            name="my light",
            unique_id="my_light",
            min_mireds=153,
            max_mireds=400,
            supported_color_modes=[color_mode],
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
    state = hass.states.get("light.test_mylight")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_mylight"},
        blocking=True,
    )
    mock_client.light_command.assert_has_calls([call(key=1, state=True, color_mode=0)])
    mock_client.light_command.reset_mock()
