"""Tests for home_connect light entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectAppliance, HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    BSH_AMBIENT_LIGHT_BRIGHTNESS,
    BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_ENABLED,
    COOKING_LIGHTING,
    COOKING_LIGHTING_BRIGHTNESS,
    REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS,
    REFRIGERATION_EXTERNAL_LIGHT_POWER,
)
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

from .conftest import get_all_appliances

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HC_APP = "Hood"

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
    ("entity_id", "status", "service", "service_data", "state", "appliance"),
    [
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    "value": True,
                },
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    "value": True,
                },
                COOKING_LIGHTING_BRIGHTNESS: {"value": 70},
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {"value": False},
                COOKING_LIGHTING_BRIGHTNESS: {"value": 70},
            },
            SERVICE_TURN_OFF,
            {},
            STATE_OFF,
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                COOKING_LIGHTING: {
                    "value": None,
                },
                COOKING_LIGHTING_BRIGHTNESS: None,
            },
            SERVICE_TURN_ON,
            {},
            STATE_UNKNOWN,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {
                    "value": True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {"value": 70},
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {"value": False},
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {"value": 70},
            },
            SERVICE_TURN_OFF,
            {},
            STATE_OFF,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                BSH_AMBIENT_LIGHT_ENABLED: {"value": True},
                BSH_AMBIENT_LIGHT_CUSTOM_COLOR: {},
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "Hood",
        ),
        (
            "light.fridgefreezer_external_light",
            {
                REFRIGERATION_EXTERNAL_LIGHT_POWER: {
                    "value": True,
                },
                REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS: {"value": 75},
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
async def test_light_functionality(
    entity_id: str,
    status: dict,
    service: str,
    service_data: dict,
    state: str,
    appliance: Mock,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test light functionality."""
    appliance.status.update(
        HomeConnectAppliance.json2dict(
            load_json_object_fixture("home_connect/settings.json")
            .get(appliance.name)
            .get("data")
            .get("settings")
        )
    )
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(status)
    service_data["entity_id"] = entity_id
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        service_data,
        blocking=True,
    )
    assert hass.states.is_state(entity_id, state)


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
                    "value": False,
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
                    "value": True,
                },
                COOKING_LIGHTING_BRIGHTNESS: {"value": 70},
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
                COOKING_LIGHTING: {"value": False},
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
                    "value": True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {"value": 70},
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
                    "value": True,
                },
                BSH_AMBIENT_LIGHT_BRIGHTNESS: {"value": 70},
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            "set_setting",
            [HomeConnectError, None, HomeConnectError, HomeConnectError],
            "Hood",
        ),
    ],
    indirect=["problematic_appliance"],
)
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
