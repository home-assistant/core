"""Tests for home_connect climate entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfPrograms,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    OptionKey,
    ProgramDefinition,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    HomeConnectApiError,
    HomeConnectError,
    SelectedProgramNotSetError,
)
from aiohomeconnect.model.program import (
    EnumerateProgram,
    EnumerateProgramConstraints,
    Execution,
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.home_connect.const import (
    BSH_POWER_ON,
    BSH_POWER_STANDBY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
    return [Platform.CLIMATE]


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
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE,
                    "Enumeration",
                )
            ],
        )
    )
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


@pytest.mark.parametrize(("appliance"), ["AirConditioner"], indirect=True)
async def test_connected_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that devices reconnected.

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
        Platform.CLIMATE,
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
        Platform.CLIMATE,
        DOMAIN,
        f"{appliance.ha_id}-air_conditioner",
    )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_climate_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if climate entities availability are based on the appliance connection state."""
    entity_ids = [
        "climate.air_conditioner",
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
    "program_keys",
    [
        [],
        [ProgramKey.LAUNDRY_CARE_DRYER_ANTI_SHRINK],
    ],
)
async def test_entity_not_added_if_no_air_conditioner_programs(
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    program_keys: list[ProgramKey],
) -> None:
    """Test that the air conditioner entity is not added if there are no air conditioner programs."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=program_key,
                raw_key=program_key.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            )
            for program_key in program_keys
        ]
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert not entity_registry.async_get("climate.air_conditioner")


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("service", "expected_setting_value"),
    [(SERVICE_TURN_ON, BSH_POWER_ON), (SERVICE_TURN_OFF, BSH_POWER_STANDBY)],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service: str,
    expected_setting_value: str,
) -> None:
    """Test turning the climate entity on and off."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        CLIMATE_DOMAIN, service, {"entity_id": "climate.air_conditioner"}, True
    )

    client.set_setting.assert_called_once_with(
        appliance.ha_id,
        setting_key=SettingKey.BSH_COMMON_POWER_STATE,
        value=expected_setting_value,
    )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("service", "expected_error"),
    [
        (SERVICE_TURN_ON, r"Error.*turn.*on.*"),
        (SERVICE_TURN_OFF, r"Error.*turn.*off.*"),
    ],
)
async def test_turn_on_off_exception(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    service: str,
    expected_error: str,
) -> None:
    """Test Home Connect exception while turning the climate entity on and off."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.set_setting.side_effect = HomeConnectError("Test error")

    with pytest.raises(HomeAssistantError, match=expected_error):
        await hass.services.async_call(
            CLIMATE_DOMAIN, service, {"entity_id": "climate.air_conditioner"}, True
        )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("program_keys", "expected_hvac_modes"),
    [
        (
            [
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_COOL,
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_DRY,
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN,
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_HEAT,
            ],
            [
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
            ],
        ),
        *[
            ([program_key], [hvac_mode])
            for program_key, hvac_mode in zip(
                [
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_COOL,
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_DRY,
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN,
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_HEAT,
                ],
                [
                    HVACMode.AUTO,
                    HVACMode.COOL,
                    HVACMode.DRY,
                    HVACMode.FAN_ONLY,
                    HVACMode.HEAT,
                ],
                strict=True,
            )
        ],
        (
            [
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_COOL,
                ProgramKey.LAUNDRY_CARE_DRYER_ANTI_SHRINK,
            ],
            [HVACMode.COOL],
        ),
    ],
)
async def test_hvac_modes_programs_mapping_and_functionality(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    expected_hvac_modes: list[HVACMode],
    program_keys: list[ProgramKey],
) -> None:
    """Test the HVAC modes to programs mapping."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=program_key,
                raw_key=program_key.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            )
            for program_key in program_keys
        ]
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get("climate.air_conditioner")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_HVAC_MODES] == expected_hvac_modes

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity.entity_id, ATTR_HVAC_MODE: expected_hvac_modes[0]},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.start_program.assert_called_once_with(
        appliance.ha_id, program_key=program_keys[0]
    )
    assert hass.states.is_state(entity.entity_id, expected_hvac_modes[0])


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_set_hvac_mode_raises_home_assistant_error_on_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that setting HVAC mode raises HomeAssistantError on API errors."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.start_program.side_effect = HomeConnectError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.air_conditioner", ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("program_keys", "expected_preset_modes"),
    [
        (
            [
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
            ],
            ["active_clean"],
        ),
        (
            [
                ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN,
                ProgramKey.LAUNDRY_CARE_DRYER_ANTI_SHRINK,
            ],
            ["active_clean"],
        ),
    ],
)
async def test_preset_modes_programs_mapping_and_functionality(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    program_keys: list[ProgramKey],
    expected_preset_modes: list[str],
) -> None:
    """Test the preset modes to programs mapping and functionality."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
                raw_key=ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            ),
            *[
                EnumerateProgram(
                    key=program_key,
                    raw_key=program_key.value,
                    constraints=EnumerateProgramConstraints(
                        execution=Execution.SELECT_AND_START,
                    ),
                )
                for program_key in program_keys
            ],
        ]
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get("climate.air_conditioner")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_PRESET_MODES] == expected_preset_modes
    state = hass.states.get(entity.entity_id)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & ClimateEntityFeature.PRESET_MODE

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity.entity_id, ATTR_PRESET_MODE: expected_preset_modes[0]},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.start_program.assert_called_once_with(
        appliance.ha_id, program_key=program_keys[0]
    )
    entity_state = hass.states.get(entity.entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_PRESET_MODE] == expected_preset_modes[0]


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_set_preset_mode_raises_home_assistant_error_on_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that setting preset mode raises HomeAssistantError on API errors."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.start_program.side_effect = HomeConnectError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.air_conditioner",
                ATTR_PRESET_MODE: "active_clean",
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
            [FAN_AUTO, "manual"],
        ),
        (
            [
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
            ],
            [FAN_AUTO, "manual"],
        ),
        (
            [
                "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
            ],
            [FAN_AUTO],
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
async def test_fan_mode_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    allowed_values: list[str | None] | None,
    expected_fan_modes: list[str],
    appliance: HomeAppliance,
    set_active_program_options_side_effect: ActiveProgramNotSetError | None,
    set_selected_program_options_side_effect: SelectedProgramNotSetError | None,
    called_mock_method: str,
) -> None:
    """Test options functionality."""
    entity_id = "climate.air_conditioner"
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
    assert entity_state.attributes[ATTR_FAN_MODES] == expected_fan_modes

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: expected_fan_modes[0],
        },
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
    assert entity_state.attributes[ATTR_FAN_MODE] == expected_fan_modes[0]


async def test_set_fan_mode_raises_home_assistant_error_on_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that setting a fan mode raises HomeAssistantError on API errors."""
    entity_id = "climate.air_conditioner"
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
            options=[
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    "Enumeration",
                    constraints=ProgramDefinitionConstraints(
                        allowed_values=[
                            "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
                            "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
                        ]
                    ),
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.set_active_program_option.side_effect = HomeConnectError("Test error")
    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_FAN_MODE: FAN_AUTO,
            },
            blocking=True,
        )


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
async def test_fan_mode_feature_supported(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that fan feature is supported depending on the fan speed mode option availability."""
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
            options=[
                ProgramDefinitionOption(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    "Enumeration",
                    constraints=ProgramDefinitionConstraints(
                        allowed_values=[
                            "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
                            "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
                        ]
                    ),
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = "climate.air_conditioner"
    state = hass.states.get(entity_id)
    assert state

    assert state.attributes[ATTR_SUPPORTED_FEATURES] & ClimateEntityFeature.FAN_MODE

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
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & ClimateEntityFeature.FAN_MODE


@pytest.mark.parametrize("appliance", ["AirConditioner"], indirect=True)
@pytest.mark.parametrize(
    ("program_keys"),
    [
        [ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO],
        [
            ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
            ProgramKey.LAUNDRY_CARE_DRYER_ANTI_SHRINK,
        ],
    ],
)
async def test_preset_mode_feature_not_supported_on_missing_active_clean(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    program_keys: list[ProgramKey],
) -> None:
    """Test that the preset modes are not supported if active clean program is missing."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=program_key,
                raw_key=program_key.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            )
            for program_key in program_keys
        ]
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("climate.air_conditioner")
    assert state
    assert (
        not state.attributes[ATTR_SUPPORTED_FEATURES] & ClimateEntityFeature.PRESET_MODE
    )
