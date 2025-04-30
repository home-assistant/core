"""Tests for Home Connect entity base classes."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfHomeAppliances,
    ArrayOfPrograms,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    Option,
    OptionKey,
    Program,
    ProgramDefinition,
    ProgramKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    HomeConnectError,
    SelectedProgramNotSetError,
)
from aiohomeconnect.model.program import (
    EnumerateProgram,
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
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
            "Dishwasher",
            {
                OptionKey.DISHCARE_DISHWASHER_HALF_LOAD: "switch.dishwasher_half_load",
                OptionKey.DISHCARE_DISHWASHER_SILENCE_ON_DEMAND: "switch.dishwasher_silence_on_demand",
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
    array_of_programs_program_arg: str,
    event_key: EventKey,
    appliance: HomeAppliance,
    option_entity_id: dict[OptionKey, str],
    options_state_stage_1: list[tuple[str, bool | None]],
    options_availability_stage_2: list[bool],
    option_without_default: tuple[OptionKey, str],
    option_without_constraints: tuple[OptionKey, str],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the options are correctly retrieved at the start and updated on program updates."""
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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
    # Every time the program is updated, the available options should use the default value if existing
    for entity_id, available in zip(
        option_entity_id.values(), options_availability_stage_2, strict=True
    ):
        assert hass.states.is_state(
            entity_id, STATE_OFF if available else STATE_UNAVAILABLE
        )
    for _, entity_id in (option_without_default, option_without_constraints):
        assert hass.states.is_state(entity_id, STATE_UNKNOWN)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
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
    array_of_programs_program_arg: str,
    event_key: EventKey,
    appliance: HomeAppliance,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
            "Dishwasher",
            OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
            "switch.dishwasher_half_load",
        )
    ],
    indirect=["appliance"],
)
async def test_program_options_retrieval_after_appliance_connection(
    event_key: EventKey,
    appliance: HomeAppliance,
    option_key: OptionKey,
    option_entity_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the options are correctly retrieved at the start and updated on program updates."""
    array_of_home_appliances = client.get_home_appliances.return_value

    async def get_home_appliances_with_options_mock() -> ArrayOfHomeAppliances:
        return ArrayOfHomeAppliances(
            [
                appliance
                for appliance in array_of_home_appliances.homeappliances
                if appliance.ha_id != appliance.ha_id
            ]
        )

    client.get_home_appliances = AsyncMock(
        side_effect=get_home_appliances_with_options_mock
    )
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[],
        )
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
    set_active_program_option_side_effect: HomeConnectError | None,
    set_selected_program_option_side_effect: HomeConnectError | None,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
