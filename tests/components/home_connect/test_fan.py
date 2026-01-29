"""Tests for home_connect fan entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    OptionKey,
    ProgramDefinition,
    ProgramKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    HomeConnectApiError,
    HomeConnectError,
    SelectedProgramNotSetError,
)
from aiohomeconnect.model.program import (
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.FAN]


@pytest.fixture(autouse=True)
def get_available_program_fixture(
    client: MagicMock,
) -> None:
    """Mock get_available_program."""
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    "Enumeration",
                ),
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
                    "Enumeration",
                ),
            ],
        )
    )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

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

    # Now that everything related to the device is removed, pair it again
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


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_connected_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that devices reconnect.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_settings_original_mock = client.get_settings
    get_all_programs_mock = client.get_all_programs

    async def get_settings_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_settings_original_mock.side_effect(ha_id)

    async def get_all_programs_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_all_programs_mock.side_effect(ha_id)

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    client.get_all_programs = AsyncMock(side_effect=get_all_programs_side_effect)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock
    client.get_all_programs = get_all_programs_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    assert not entity_registry.async_get_entity_id(
        Platform.FAN,
        DOMAIN,
        f"{appliance.ha_id}-air_conditioner",
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

    assert entity_registry.async_get_entity_id(
        Platform.FAN,
        DOMAIN,
        f"{appliance.ha_id}-air_conditioner",
    )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_fan_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if fan entities availability are based on the appliance connection state."""
    entity_ids = [
        "fan.air_conditioner",
    ]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

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


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    (
        "set_active_program_options_side_effect",
        "set_selected_program_options_side_effect",
        "called_mock_method",
    ),
    [
        (
            None,
            SelectedProgramNotSetError("error.key"),
            "set_active_program_option",
        ),
        (
            ActiveProgramNotSetError("error.key"),
            None,
            "set_selected_program_option",
        ),
    ],
)
async def test_speed_percentage_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    set_active_program_options_side_effect: ActiveProgramNotSetError | None,
    set_selected_program_options_side_effect: SelectedProgramNotSetError | None,
    called_mock_method: str,
) -> None:
    """Test speed percentage functionality."""
    entity_id = "fan.air_conditioner"
    option_key = OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE
    if set_active_program_options_side_effect:
        client.set_active_program_option.side_effect = (
            set_active_program_options_side_effect
        )
    else:
        assert set_selected_program_options_side_effect
        client.set_selected_program_option.side_effect = (
            set_selected_program_options_side_effect
        )
    called_mock: AsyncMock = getattr(client, called_mock_method)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.is_state(entity_id, "50")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PERCENTAGE: 50,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    called_mock.assert_called_once_with(
        appliance.ha_id,
        option_key=option_key,
        value=50,
    )
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_PERCENTAGE] == 50


async def test_set_speed_raises_home_assistant_error_on_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that setting a fan mode raises HomeAssistantError on API errors."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.set_active_program_option.side_effect = HomeConnectError("Test error")
    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: "fan.air_conditioner",
                ATTR_PERCENTAGE: 50,
            },
            blocking=True,
        )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    (
        "set_active_program_options_side_effect",
        "set_selected_program_options_side_effect",
        "called_mock_method",
    ),
    [
        (
            None,
            SelectedProgramNotSetError("error.key"),
            "set_active_program_option",
        ),
        (
            ActiveProgramNotSetError("error.key"),
            None,
            "set_selected_program_option",
        ),
    ],
)
@pytest.mark.parametrize(
    ("allowed_values", "expected_fan_modes"),
    [
        (
            None,
            ["auto", "manual"],
        ),
        (
            [
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
            ],
            ["auto", "manual"],
        ),
        (
            [
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
            ],
            ["auto"],
        ),
        (
            [
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
                "A.Non.Documented.Option",
            ],
            ["manual"],
        ),
    ],
)
async def test_preset_mode_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    allowed_values: list[str | None] | None,
    expected_fan_modes: list[str],
    set_active_program_options_side_effect: ActiveProgramNotSetError | None,
    set_selected_program_options_side_effect: SelectedProgramNotSetError | None,
    called_mock_method: str,
) -> None:
    """Test preset mode functionality."""
    entity_id = "fan.air_conditioner"
    option_key = (
        OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
    )
    if set_active_program_options_side_effect:
        client.set_active_program_option.side_effect = (
            set_active_program_options_side_effect
        )
    else:
        assert set_selected_program_options_side_effect
        client.set_selected_program_option.side_effect = (
            set_selected_program_options_side_effect
        )
    called_mock: AsyncMock = getattr(client, called_mock_method)
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
            options=[
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    "Enumeration",
                    constraints=ProgramDefinitionConstraints(
                        allowed_values=allowed_values
                    ),
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_PRESET_MODES] == expected_fan_modes
    assert entity_state.attributes[ATTR_PRESET_MODE] != expected_fan_modes[0]

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PRESET_MODE: expected_fan_modes[0],
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    called_mock.assert_called_once_with(
        appliance.ha_id,
        option_key=option_key,
        value=allowed_values[0]
        if allowed_values
        else "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
    )
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_PRESET_MODE] == expected_fan_modes[0]


async def test_set_preset_mode_raises_home_assistant_error_on_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that setting a fan mode raises HomeAssistantError on API errors."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.set_active_program_option.side_effect = HomeConnectError("Test error")
    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.air_conditioner",
                ATTR_PRESET_MODE: "auto",
            },
            blocking=True,
        )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("option_key", "expected_fan_feature"),
    [
        (
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
            FanEntityFeature.PRESET_MODE,
        ),
        (
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
            FanEntityFeature.SET_SPEED,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    option_key: OptionKey,
    expected_fan_feature: FanEntityFeature,
) -> None:
    """Test that supported features are detected correctly."""
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    option_key,
                    "Enumeration",
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = "fan.air_conditioner"
    state = hass.states.get(entity_id)
    assert state

    assert state.attributes[ATTR_SUPPORTED_FEATURES] & expected_fan_feature

    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[],
        )
    )
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.NOTIFY,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                            raw_key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.UNKNOWN.value,
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & expected_fan_feature


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_added_entity_automatically(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that no fan entity is created if no fan options are available but when they are added later, the entity is created."""
    entity_id = "fan.air_conditioner"
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    OptionKey.LAUNDRY_CARE_WASHER_SPIN_SPEED,
                    "Enumeration",
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert not hass.states.get(entity_id)

    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
            options=[
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    "Enumeration",
                ),
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
                    "Enumeration",
                ),
            ],
        )
    )
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.NOTIFY,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                            raw_key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO.value,
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id)
