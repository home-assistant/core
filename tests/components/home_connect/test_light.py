"""Tests for home_connect light entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfSettings,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectApiError, HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
    DOMAIN,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


@pytest.mark.parametrize("appliance", ["Hood"], indirect=True)
async def test_paired_depaired_devices_flow(
    appliance: HomeAppliance,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize(
    ("appliance", "keys_to_check"),
    [
        (
            "Hood",
            (SettingKey.COOKING_COMMON_LIGHTING,),
        )
    ],
    indirect=["appliance"],
)
async def test_connected_devices(
    appliance: HomeAppliance,
    keys_to_check: tuple,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_settings_original_mock = client.get_settings

    async def get_settings_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_settings_original_mock.side_effect(ha_id)

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.LIGHT,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for key in keys_to_check:
        assert entity_registry.async_get_entity_id(
            Platform.LIGHT,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.parametrize("appliance", ["Hood"], indirect=True)
async def test_light_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
) -> None:
    """Test if light entities availability are based on the appliance connection state."""
    entity_ids = [
        "light.hood_functional_light",
    ]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    (
        "entity_id",
        "set_settings_args",
        "service",
        "exprected_attributes",
        "state",
        "appliance",
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
            {ATTR_BRIGHTNESS: 199},
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
            {ATTR_BRIGHTNESS: 199},
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
                ATTR_RGB_COLOR: (255, 255, 0),
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
                ATTR_HS_COLOR: (255.484, 15.196),
                ATTR_BRIGHTNESS: 199,
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
    indirect=["appliance"],
)
async def test_light_functionality(
    entity_id: str,
    set_settings_args: dict[SettingKey, Any],
    service: str,
    exprected_attributes: dict[str, Any],
    state: str,
    appliance: HomeAppliance,
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
    service_data[ATTR_ENTITY_ID] = entity_id
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {key: value for key, value in service_data.items() if value is not None},
    )
    await hass.async_block_till_done()
    client.set_setting.assert_has_calls(
        [
            call(appliance.ha_id, setting_key=setting_key, value=value)
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
        "appliance",
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
    indirect=["appliance"],
)
async def test_light_color_different_than_custom(
    entity_id: str,
    events: dict[EventKey, Any],
    appliance: HomeAppliance,
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
            ATTR_RGB_COLOR: (255, 255, 0),
            ATTR_ENTITY_ID: entity_id,
        },
    )
    await hass.async_block_till_done()
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
    assert entity_state.attributes[ATTR_RGB_COLOR] is not None
    assert entity_state.attributes[ATTR_HS_COLOR] is not None

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
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
    assert entity_state.attributes[ATTR_RGB_COLOR] is None
    assert entity_state.attributes[ATTR_HS_COLOR] is None


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
            {ATTR_BRIGHTNESS: 200},
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
            {ATTR_BRIGHTNESS: 200},
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
            {ATTR_RGB_COLOR: (255, 255, 0)},
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
            {ATTR_RGB_COLOR: (255, 255, 0)},
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
                ATTR_HS_COLOR: (255.484, 15.196),
                ATTR_BRIGHTNESS: 199,
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

    service_data[ATTR_ENTITY_ID] = entity_id
    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            LIGHT_DOMAIN, service, service_data, blocking=True
        )
    assert client_with_exception.set_setting.call_count == len(attr_side_effect)
