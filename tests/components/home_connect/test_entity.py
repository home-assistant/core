"""Tests for Home Connect entity base classes."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ApplianceType,
    ArrayOfEvents,
    ArrayOfPrograms,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    Option,
    OptionKey,
    Program,
    ProgramDefinition,
    ProgramKey,
    SettingKey,
    Status,
    StatusKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    ConflictError,
    HomeConnectError,
    NoProgramActiveError,
    SelectedProgramNotSetError,
    UnauthorizedError,
)
from aiohomeconnect.model.program import (
    EnumerateProgram,
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    ("array_of_programs_program_arg", "event_key"),
    [
        (
            "active",
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        ),
        (
            "selected",
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "appliance",
        "option_entity_id",
        "options_state_stage_1",
        "options_availability_stage_2",
        "option_without_default",
        "option_without_constraints",
    ),
    [
        (
            ApplianceType.DISHWASHER,
            {
                OptionKey.DISHCARE_DISHWASHER_HALF_LOAD: "switch.dishwasher_half_load",
                OptionKey.DISHCARE_DISHWASHER_SILENCE_ON_DEMAND: (
                    "switch.dishwasher_silence_on_demand"
                ),
                OptionKey.DISHCARE_DISHWASHER_ECO_DRY: "switch.dishwasher_eco_dry",
            },
            [(STATE_ON, True), (STATE_OFF, False), (None, None)],
            [False, True, True],
            (
                OptionKey.DISHCARE_DISHWASHER_HYGIENE_PLUS,
                "switch.dishwasher_hygiene",
            ),
            (OptionKey.DISHCARE_DISHWASHER_EXTRA_DRY, "switch.dishwasher_extra_dry"),
        )
    ],
    indirect=["appliance"],
)
async def test_program_options_retrieval(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    array_of_programs_program_arg: str,
    event_key: EventKey,
    appliance: HomeAppliance,
    option_entity_id: dict[OptionKey, str],
    options_state_stage_1: list[tuple[str, bool | None]],
    options_availability_stage_2: list[bool],
    option_without_default: tuple[OptionKey, str],
    option_without_constraints: tuple[OptionKey, str],
) -> None:
    """Test options are retrieved at start and updated on programs."""
    original_get_all_programs_mock = client.get_all_programs.side_effect
    options_values = [
        Option(
            option_key,
            value,
        )
        for option_key, (_, value) in zip(
            option_entity_id.keys(), options_state_stage_1, strict=True
        )
        if value is not None
    ]

    async def get_all_programs_with_options_mock(ha_id: str) -> ArrayOfPrograms:
        if ha_id != appliance.ha_id:
            return await original_get_all_programs_mock(ha_id)

        array_of_programs: ArrayOfPrograms = await original_get_all_programs_mock(ha_id)
        return ArrayOfPrograms(
            **(
                {
                    "programs": array_of_programs.programs,
                    array_of_programs_program_arg: Program(
                        array_of_programs.programs[0].key, options=options_values
                    ),
                }
            )
        )

    client.get_all_programs = AsyncMock(side_effect=get_all_programs_with_options_mock)
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    option_key,
                    "Boolean",
                    constraints=ProgramDefinitionConstraints(
                        default=False,
                    ),
                )
                for option_key, (_, value) in zip(
                    option_entity_id.keys(), options_state_stage_1, strict=True
                )
                if value is not None
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id, (state, _) in zip(
        option_entity_id.values(), options_state_stage_1, strict=True
    ):
        if state is not None:
            assert hass.states.is_state(entity_id, state)
        else:
            assert not hass.states.get(entity_id)

    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                *[
                    ProgramDefinitionOption(
                        option_key,
                        "Boolean",
                        constraints=ProgramDefinitionConstraints(
                            default=False,
                        ),
                    )
                    for option_key, available in zip(
                        option_entity_id.keys(),
                        options_availability_stage_2,
                        strict=True,
                    )
                    if available
                ],
                ProgramDefinitionOption(
                    option_without_default[0],
                    "Boolean",
                    constraints=ProgramDefinitionConstraints(),
                ),
                ProgramDefinitionOption(
                    option_without_constraints[0],
                    "Boolean",
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
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.DISHCARE_DISHWASHER_AUTO_1,
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    # Verify default values
    # Every time the program is updated, the available options should use the default
    # value if existing
    for entity_id, available in zip(
        option_entity_id.values(), options_availability_stage_2, strict=True
    ):
        assert hass.states.is_state(
            entity_id, STATE_OFF if available else STATE_UNAVAILABLE
        )
    for _, entity_id in (option_without_default, option_without_constraints):
        assert hass.states.is_state(entity_id, STATE_UNKNOWN)


@pytest.mark.parametrize("appliance", [ApplianceType.WASHER], indirect=True)
@pytest.mark.parametrize(
    ("array_of_programs_program_arg", "event_key"),
    [
        (
            "active",
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        ),
        (
            "selected",
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ),
    ],
)
async def test_no_options_retrieval_on_unknown_program(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    array_of_programs_program_arg: str,
    event_key: EventKey,
) -> None:
    """Test that no options are retrieved when the program is unknown."""

    async def get_all_programs_with_options_mock(ha_id: str) -> ArrayOfPrograms:
        return ArrayOfPrograms(
            **(
                {
                    "programs": [
                        EnumerateProgram(ProgramKey.UNKNOWN, "unknown program")
                    ],
                    array_of_programs_program_arg: Program(
                        ProgramKey.UNKNOWN, options=[]
                    ),
                }
            )
        )

    client.get_all_programs = AsyncMock(side_effect=get_all_programs_with_options_mock)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert client.get_available_program.call_count == 0

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.NOTIFY,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.UNKNOWN,
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    assert client.get_available_program.call_count == 0


@pytest.mark.parametrize(
    "event_key",
    [
        EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
    ],
)
@pytest.mark.parametrize(
    ("appliance", "option_key", "option_entity_id"),
    [
        (
            ApplianceType.DISHWASHER,
            OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
            "switch.dishwasher_half_load",
        )
    ],
    indirect=["appliance"],
)
async def test_program_options_retrieval_after_appliance_connection(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    event_key: EventKey,
    appliance: HomeAppliance,
    option_key: OptionKey,
    option_entity_id: str,
) -> None:
    """Test options are retrieved at start and updated on programs."""
    appliance.connected = False
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert not hass.states.get(option_entity_id)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
                            raw_key=EventKey.BSH_COMMON_APPLIANCE_CONNECTED.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value="",
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    assert not hass.states.get(option_entity_id)

    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    option_key,
                    "Boolean",
                    constraints=ProgramDefinitionConstraints(
                        default=False,
                    ),
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
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.DISHCARE_DISHWASHER_AUTO_1,
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.get(option_entity_id)


@pytest.mark.parametrize(
    (
        "set_active_program_option_side_effect",
        "set_selected_program_option_side_effect",
    ),
    [
        (
            ActiveProgramNotSetError("error.key"),
            SelectedProgramNotSetError("error.key"),
        ),
        (
            HomeConnectError(),
            None,
        ),
        (
            ActiveProgramNotSetError("error.key"),
            HomeConnectError(),
        ),
    ],
)
async def test_option_entity_functionality_exception(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    set_active_program_option_side_effect: HomeConnectError | None,
    set_selected_program_option_side_effect: HomeConnectError | None,
) -> None:
    """Test that the option entity handles exceptions correctly."""
    entity_id = "switch.washer_i_dos_1_active"

    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE,
                    "Boolean",
                )
            ],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get(entity_id)

    if set_active_program_option_side_effect:
        client.set_active_program_option = AsyncMock(
            side_effect=set_active_program_option_side_effect
        )
    if set_selected_program_option_side_effect:
        client.set_selected_program_option = AsyncMock(
            side_effect=set_selected_program_option_side_effect
        )

    with pytest.raises(HomeAssistantError, match=r"Error.*setting.*option.*"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    (
        "platforms",
        "appliance",
        "entity_id",
        "key",
        "client_method",
        "client_key_arg",
        "client_method_return_value",
    ),
    [
        (
            [Platform.SWITCH],
            ApplianceType.WASHER,
            "switch.washer_power",
            SettingKey.BSH_COMMON_POWER_STATE,
            "get_setting",
            "setting_key",
            GetSetting(
                SettingKey.BSH_COMMON_POWER_STATE,
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.Off",
            ),
        ),
        (
            [Platform.BINARY_SENSOR],
            ApplianceType.WASHER,
            "binary_sensor.washer_remote_control",
            StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,
            "get_status_value",
            "status_key",
            Status(
                StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,
                "BSH.Common.Status.RemoteControlActive",
                False,
            ),
        ),
    ],
    indirect=["appliance"],
    ids=["setting entity", "status entity"],
)
async def test_entity_async_update_by_key_type(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    key: SettingKey | StatusKey,
    client_method: str,
    client_key_arg: str,
    client_method_return_value: GetSetting | Status,
) -> None:
    """Test entity updates fetch a setting or status by its key type."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})

    assert hass.states.is_state(entity_id, STATE_ON)

    setattr(
        client,
        client_method,
        method := AsyncMock(return_value=client_method_return_value),
    )

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    method.assert_awaited_once_with(appliance.ha_id, **{client_key_arg: key})
    assert hass.states.is_state(entity_id, STATE_OFF)


@pytest.mark.parametrize(
    ("get_active_program_option_side_effect", "expected_state"),
    [
        (None, STATE_ON),
        (NoProgramActiveError("error.key"), STATE_OFF),
    ],
    ids=["active program", "selected program"],
)
@pytest.mark.parametrize("appliance", [ApplianceType.WASHER], indirect=True)
async def test_option_entity_async_update(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    get_active_program_option_side_effect: NoProgramActiveError | None,
    expected_state: str,
) -> None:
    """Test option updates use active program data or fall back to selected."""
    option_key = OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE
    entity_id = "switch.washer_i_dos_1_active"
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[ProgramDefinitionOption(option_key, "Boolean")],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(entity_id)

    client.get_active_program_option = AsyncMock(
        side_effect=get_active_program_option_side_effect,
        return_value=Option(option_key, True),
    )
    client.get_selected_program_option = AsyncMock(
        return_value=Option(option_key, False),
    )

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    client.get_active_program_option.assert_awaited_once_with(
        appliance.ha_id, option_key=option_key
    )
    if get_active_program_option_side_effect:
        client.get_selected_program_option.assert_awaited_once_with(
            appliance.ha_id, option_key=option_key
        )
    else:
        client.get_selected_program_option.assert_not_awaited()
    assert hass.states.is_state(entity_id, expected_state)


@pytest.mark.parametrize(
    ("platforms", "appliance", "entity_id"),
    [
        (
            [Platform.BINARY_SENSOR],
            ApplianceType.WASHER,
            "binary_sensor.washer_connectivity",
        ),
        (
            [Platform.SENSOR],
            ApplianceType.DISHWASHER,
            "sensor.dishwasher_program_aborted",
        ),
        (
            [Platform.BUTTON],
            ApplianceType.DISHWASHER,
            "button.dishwasher_stop_program",
        ),
    ],
    indirect=["appliance"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_async_update_with_non_data_key(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
) -> None:
    """Test entities using event or string keys use the coordinator refresh."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(entity_id)

    coordinator = config_entry.runtime_data.appliance_coordinators[appliance.ha_id]
    coordinator.async_request_refresh = AsyncMock()
    client.get_setting.reset_mock()
    client.get_status_value.reset_mock()
    client.get_active_program_option.reset_mock()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    ("platforms", "appliance", "entity_id", "key", "client_method"),
    [
        (
            [Platform.SWITCH],
            ApplianceType.WASHER,
            "switch.washer_power",
            SettingKey.BSH_COMMON_POWER_STATE,
            "get_setting",
        ),
        (
            [Platform.BINARY_SENSOR],
            ApplianceType.WASHER,
            "binary_sensor.washer_remote_control",
            StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,
            "get_status_value",
        ),
        (
            [Platform.SWITCH],
            ApplianceType.WASHER,
            "switch.washer_i_dos_1_active",
            OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE,
            "get_active_program_option",
        ),
        (
            [Platform.SWITCH],
            ApplianceType.WASHER,
            "switch.washer_i_dos_1_active",
            OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE,
            "get_selected_program_option",
        ),
    ],
    indirect=["appliance"],
    ids=[
        "setting entity",
        "status entity",
        "active program option entity",
        "selected program option entity",
    ],
)
async def test_entity_async_update_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
    key: SettingKey | StatusKey | OptionKey,
    client_method: str,
) -> None:
    """Test API errors while updating an entity use the translated error."""
    if isinstance(key, OptionKey):
        client.get_available_program = AsyncMock(
            return_value=ProgramDefinition(
                ProgramKey.UNKNOWN,
                options=[ProgramDefinitionOption(key, "Boolean")],
            )
        )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(entity_id)

    error = HomeConnectError("error.key")
    client.get_active_program_option = AsyncMock(
        side_effect=NoProgramActiveError("error.key")
    )
    setattr(client, client_method, AsyncMock(side_effect=error))

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    assert f"Error fetching state of {entity_id}: {error}" in caplog.text


@pytest.mark.parametrize("appliance", [ApplianceType.WASHER], indirect=True)
async def test_entity_async_update_unsupported_setting_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test unsupported settings become unavailable and recover on update."""
    entity_id = "switch.washer_power"
    setting_key = SettingKey.BSH_COMMON_POWER_STATE

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.is_state(entity_id, STATE_ON)

    client.get_setting = AsyncMock(
        side_effect=ConflictError("SDK.Error.UnsupportedSetting")
    )
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    client.get_setting = AsyncMock(
        return_value=GetSetting(
            setting_key,
            setting_key.value,
            "BSH.Common.EnumType.PowerState.Off",
        )
    )
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.is_state(entity_id, STATE_OFF)


@pytest.mark.parametrize(
    ("platforms", "entity_id", "client_method"),
    [
        ([Platform.SWITCH], "switch.washer_power", "get_setting"),
        (
            [Platform.BINARY_SENSOR],
            "binary_sensor.washer_remote_control",
            "get_status_value",
        ),
        (
            [Platform.SWITCH],
            "switch.washer_i_dos_1_active",
            "get_active_program_option",
        ),
    ],
    ids=["setting", "status", "option"],
)
@pytest.mark.parametrize("appliance", [ApplianceType.WASHER], indirect=True)
async def test_entity_async_update_unauthorized_error_starts_reauth(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    client_method: str,
) -> None:
    """Test unauthorized entity updates start reauthentication."""
    option_key = OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[ProgramDefinitionOption(option_key, "Boolean")],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(entity_id)

    method = AsyncMock(side_effect=UnauthorizedError("unauthorized"))
    setattr(client, client_method, method)

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    method.assert_awaited_once()
    flows_in_progress = hass.config_entries.flow.async_progress()
    assert len(flows_in_progress) == 1
    assert flows_in_progress[0]["context"]["entry_id"] == config_entry.entry_id
    assert flows_in_progress[0]["context"]["source"] == "reauth"


@pytest.mark.parametrize("appliance", [ApplianceType.WASHER], indirect=True)
async def test_disabled_entity_async_update_does_not_fetch_data(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test manual updates do not fetch data for a disabled entity."""
    entity_id = "switch.washer_power"

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(entity_id)

    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    client.get_setting.reset_mock()
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    client.get_setting.assert_not_awaited()
