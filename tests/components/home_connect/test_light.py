"""Tests for home_connect light entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock, call

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import ATTR_VALUE
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.util.color as color_util

from .conftest import get_all_appliances

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HC_APP = "Hood"
BSH_AMBIENT_LIGHT_BRIGHTNESS = "BSH.Common.Setting.AmbientLightBrightness"
BSH_AMBIENT_LIGHT_COLOR = "BSH.Common.Setting.AmbientLightColor"
BSH_AMBIENT_LIGHT_ENABLE_CUSTOM_COLOR = (
    "BSH.Common.EnumType.AmbientLightColor.CustomColor"
)
BSH_AMBIENT_LIGHT_CUSTOM_COLOR = "BSH.Common.Setting.AmbientLightCustomColor"
BSH_AMBIENT_LIGHT_ENABLED = "BSH.Common.Setting.AmbientLightEnabled"
COOKING_LIGHTING = "Cooking.Common.Setting.Lighting"
COOKING_LIGHTING_BRIGHTNESS = "Cooking.Common.Setting.LightingBrightness"

SETTINGS_STATUS = {
    setting.pop("key"): setting
    for setting in load_json_object_fixture("home_connect/settings.json")
    .get(TEST_HC_APP)
    .get("data")
    .get("settings")
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


async def test_light(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test switch entities."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    (
        "entity_id",
        "status",
        "state",
        "service",
        "service_data",
        "appliance",
        "expected_setting_calls",
    ),
    [
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    ATTR_VALUE: True,
                },
            },
            STATE_ON,
            SERVICE_TURN_ON,
            {},
            "Hood",
            [call(COOKING_LIGHTING, True)],
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    ATTR_VALUE: True,
                },
                COOKING_LIGHTING_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            STATE_ON,
            SERVICE_TURN_ON,
            {"brightness": 200},
            "Hood",
            [
                call(COOKING_LIGHTING, True),
                call(COOKING_LIGHTING_BRIGHTNESS, 81),
            ],
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {ATTR_VALUE: False},
                COOKING_LIGHTING_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            STATE_OFF,
            SERVICE_TURN_OFF,
            {},
            "Hood",
            [call(COOKING_LIGHTING, False)],
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    ATTR_VALUE: None,
                },
                COOKING_LIGHTING_BRIGHTNESS: None,
            },
            STATE_UNKNOWN,
            SERVICE_TURN_ON,
            {},
            "Hood",
            [call(COOKING_LIGHTING, True)],
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {
                    ATTR_VALUE: True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            STATE_ON,
            SERVICE_TURN_ON,
            {"brightness": 200},
            "Hood",
            [
                call(BSH_AMBIENT_LIGHT_ENABLED, True),
                call(BSH_AMBIENT_LIGHT_BRIGHTNESS, 81),
            ],
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {ATTR_VALUE: False},
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            STATE_OFF,
            SERVICE_TURN_OFF,
            {},
            "Hood",
            [
                call(BSH_AMBIENT_LIGHT_ENABLED, False),
            ],
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {ATTR_VALUE: True},
                BSH_AMBIENT_LIGHT_CUSTOM_COLOR: {},
            },
            STATE_ON,
            SERVICE_TURN_ON,
            {},
            "Hood",
            [call(BSH_AMBIENT_LIGHT_ENABLED, True)],
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {ATTR_VALUE: False},
                BSH_AMBIENT_LIGHT_COLOR: {
                    ATTR_VALUE: "",
                },
                BSH_AMBIENT_LIGHT_CUSTOM_COLOR: {},
            },
            STATE_OFF,
            SERVICE_TURN_ON,
            {
                "rgb_color": [255, 255, 0],
            },
            "Hood",
            [
                call(BSH_AMBIENT_LIGHT_ENABLED, True),
                call(BSH_AMBIENT_LIGHT_COLOR, BSH_AMBIENT_LIGHT_ENABLE_CUSTOM_COLOR),
                call(
                    BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
                    f"#{color_util.color_rgb_to_hex(255,255,0)}",
                ),
            ],
        ),
    ],
    indirect=["appliance"],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_light_functionality(
    entity_id: str,
    status: dict,
    state: str,
    service: str,
    service_data: dict,
    appliance: Mock,
    expected_setting_calls: tuple,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test light functionality."""
    appliance.status.update(SETTINGS_STATUS)
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(status)
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, state)

    service_data["entity_id"] = entity_id
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()
    appliance.set_setting.assert_has_calls(expected_setting_calls)


@pytest.mark.parametrize(
    (
        "entity_id",
        "status",
        "service",
        "service_data",
        "mock_attr",
        "attr_side_effect",
        "problematic_appliance",
    ),
    [
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    ATTR_VALUE: False,
                },
            },
            SERVICE_TURN_ON,
            {},
            "set_setting",
            [HomeConnectError, HomeConnectError],
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    ATTR_VALUE: True,
                },
                COOKING_LIGHTING_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            "set_setting",
            [HomeConnectError, HomeConnectError],
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {ATTR_VALUE: False},
            },
            SERVICE_TURN_OFF,
            {},
            "set_setting",
            [HomeConnectError, HomeConnectError],
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {
                    ATTR_VALUE: True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            SERVICE_TURN_ON,
            {},
            "set_setting",
            [HomeConnectError, HomeConnectError],
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {
                    ATTR_VALUE: True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {ATTR_VALUE: 70},
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            "set_setting",
            [HomeConnectError, None, HomeConnectError],
            "Hood",
        ),
    ],
    indirect=["problematic_appliance"],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_switch_exception_handling(
    entity_id: str,
    status: dict,
    service: str,
    service_data: dict,
    mock_attr: str,
    attr_side_effect: list,
    problematic_appliance: Mock,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test light exception handling."""
    problematic_appliance.status.update(SETTINGS_STATUS)
    problematic_appliance.set_setting.side_effect = attr_side_effect
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    problematic_appliance.status.update(status)
    service_data["entity_id"] = entity_id
    await hass.services.async_call(LIGHT_DOMAIN, service, service_data, blocking=True)
    assert getattr(problematic_appliance, mock_attr).call_count == len(attr_side_effect)
