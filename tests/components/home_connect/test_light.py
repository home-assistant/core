"""Tests for home_connect light entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, call

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfSettings,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TEST_HC_APP = "Hood"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


async def test_light(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test switch entities."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    (
        "entity_id",
        "set_settings_args",
        "service",
        "exprected_attributes",
        "state",
        "appliance_ha_id",
    ),
    [
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: True,
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: True,
                SettingKey.COOKING_COMMON_LIGHTING_BRIGHTNESS: 80,
            },
            SERVICE_TURN_ON,
            {"brightness": 199},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: False,
            },
            SERVICE_TURN_OFF,
            {},
            STATE_OFF,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS: 80,
            },
            SERVICE_TURN_ON,
            {"brightness": 199},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: False,
            },
            SERVICE_TURN_OFF,
            {},
            STATE_OFF,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR: BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR: "#ffff00",
            },
            SERVICE_TURN_ON,
            {
                "rgb_color": (255, 255, 0),
            },
            STATE_ON,
            "Hood",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR: BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR: "#b5adcc",
            },
            SERVICE_TURN_ON,
            {
                "hs_color": (255.484, 15.196),
                "brightness": 199,
            },
            STATE_ON,
            "Hood",
        ),
        (
            "light.fridgefreezer_external_light",
            {
                SettingKey.REFRIGERATION_COMMON_LIGHT_EXTERNAL_POWER: True,
            },
            SERVICE_TURN_ON,
            {},
            STATE_ON,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_light_functionality(
    entity_id: str,
    set_settings_args: dict[SettingKey, Any],
    service: str,
    exprected_attributes: dict[str, Any],
    state: str,
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test light functionality."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    service_data = exprected_attributes.copy()
    service_data["entity_id"] = entity_id
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {key: value for key, value in service_data.items() if value is not None},
    )
    await hass.async_block_till_done()
    client.set_setting.assert_has_calls(
        [
            call(appliance_ha_id, setting_key=setting_key, value=value)
            for setting_key, value in set_settings_args.items()
        ]
    )
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == state
    for key, value in exprected_attributes.items():
        assert entity_state.attributes[key] == value


@pytest.mark.parametrize(
    (
        "entity_id",
        "events",
        "appliance_ha_id",
    ),
    [
        (
            "light.hood_ambient_light",
            {
                EventKey.BSH_COMMON_SETTING_AMBIENT_LIGHT_COLOR: "BSH.Common.EnumType.AmbientLightColor.Color1",
            },
            "Hood",
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_light_color_different_than_custom(
    entity_id: str,
    events: dict[EventKey, Any],
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that light color attributes are not set if color is different than custom."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            "rgb_color": (255, 255, 0),
            "entity_id": entity_id,
        },
    )
    await hass.async_block_till_done()
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
    assert entity_state.attributes["rgb_color"] is not None
    assert entity_state.attributes["hs_color"] is not None

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.NOTIFY,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=value,
                        )
                        for event_key, value in events.items()
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
    assert entity_state.attributes["rgb_color"] is None
    assert entity_state.attributes["hs_color"] is None


@pytest.mark.parametrize(
    (
        "entity_id",
        "setting",
        "service",
        "service_data",
        "attr_side_effect",
        "exception_match",
    ),
    [
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: True,
            },
            SERVICE_TURN_ON,
            {},
            [HomeConnectError, HomeConnectError],
            r"Error.*turn.*on.*",
        ),
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: True,
                SettingKey.COOKING_COMMON_LIGHTING_BRIGHTNESS: 70,
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            [HomeConnectError, HomeConnectError],
            r"Error.*turn.*on.*",
        ),
        (
            "light.hood_functional_light",
            {
                SettingKey.COOKING_COMMON_LIGHTING: False,
            },
            SERVICE_TURN_OFF,
            {},
            [HomeConnectError, HomeConnectError],
            r"Error.*turn.*off.*",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS: 70,
            },
            SERVICE_TURN_ON,
            {},
            [HomeConnectError, HomeConnectError],
            r"Error.*turn.*on.*",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS: 70,
            },
            SERVICE_TURN_ON,
            {"brightness": 200},
            [HomeConnectError, None, HomeConnectError],
            r"Error.*set.*brightness.*",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS: 70,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR: 70,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR: "#ffff00",
            },
            SERVICE_TURN_ON,
            {"rgb_color": (255, 255, 0)},
            [HomeConnectError, None, HomeConnectError],
            r"Error.*select.*custom color.*",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_BRIGHTNESS: 70,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR: BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR: "#ffff00",
            },
            SERVICE_TURN_ON,
            {"rgb_color": (255, 255, 0)},
            [HomeConnectError, None, None, HomeConnectError],
            r"Error.*set.*color.*",
        ),
        (
            "light.hood_ambient_light",
            {
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED: True,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR: BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
                SettingKey.BSH_COMMON_AMBIENT_LIGHT_CUSTOM_COLOR: "#b5adcc",
            },
            SERVICE_TURN_ON,
            {
                "hs_color": (255.484, 15.196),
                "brightness": 199,
            },
            [HomeConnectError, None, None, HomeConnectError],
            r"Error.*set.*color.*",
        ),
    ],
)
async def test_light_exception_handling(
    entity_id: str,
    setting: dict[SettingKey, dict[str, Any]],
    service: str,
    service_data: dict,
    attr_side_effect: list[type[HomeConnectError] | None],
    exception_match: str,
    hass: HomeAssistant,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test light exception handling."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=setting_key,
                raw_key=setting_key.value,
                value=value,
            )
            for setting_key, value in setting.items()
        ]
    )
    client_with_exception.set_setting.side_effect = [
        exception() if exception else None for exception in attr_side_effect
    ]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        await client_with_exception.set_setting()

    service_data["entity_id"] = entity_id
    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            LIGHT_DOMAIN, service, service_data, blocking=True
        )
    assert client_with_exception.set_setting.call_count == len(attr_side_effect)
