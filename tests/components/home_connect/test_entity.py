"""Tests for Home Connect entity base classes."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfOptions,
    ArrayOfPrograms,
    Event,
    EventKey,
    EventMessage,
    EventType,
    Option,
    OptionKey,
    Program,
    ProgramKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    HomeConnectError,
    SelectedProgramNotSetError,
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
    ("array_of_programs_program_arg", "retrieve_options_method", "event_key"),
    [
        (
            "active",
            "get_active_program_options",
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        ),
        (
            "selected",
            "get_selected_program_options",
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "appliance_ha_id",
        "option_entity_id",
        "options_state_stage_1",
        "options_state_stage_2",
    ),
    [
        (
            "Dishwasher",
            {
                OptionKey.DISHCARE_DISHWASHER_HALF_LOAD: "switch.dishwasher_half_load",
                OptionKey.DISHCARE_DISHWASHER_SILENCE_ON_DEMAND: "switch.dishwasher_silence_on_demand",
                OptionKey.DISHCARE_DISHWASHER_ECO_DRY: "switch.dishwasher_eco_dry",
            },
            [(STATE_ON, True), (STATE_OFF, False), (STATE_UNAVAILABLE, None)],
            [(STATE_UNAVAILABLE, None), (STATE_ON, True), (STATE_OFF, False)],
        )
    ],
    indirect=["appliance_ha_id"],
)
async def test_program_options_retrieval(
    array_of_programs_program_arg: str,
    retrieve_options_method: str,
    event_key: EventKey,
    appliance_ha_id: str,
    option_entity_id: dict[OptionKey, str],
    options_state_stage_1: list[tuple[str, bool | None]],
    options_state_stage_2: list[tuple[str, bool | None]],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the options are correctly retrieved at the start and updated on program updates."""
    assert options_state_stage_1 != options_state_stage_2, (
        "available options should differ between stages"
    )
    original_get_all_programs_mock = client.get_all_programs.side_effect
    options_stages = [
        [
            Option(
                option_key,
                value,
            )
            for option_key, (_, value) in zip(
                option_entity_id.keys(), options_state_stage, strict=True
            )
            if value is not None
        ]
        for options_state_stage in (options_state_stage_1, options_state_stage_2)
    ]

    async def get_all_programs_with_options_mock(ha_id: str) -> ArrayOfPrograms:
        if ha_id != appliance_ha_id:
            return await original_get_all_programs_mock(ha_id)

        array_of_programs: ArrayOfPrograms = await original_get_all_programs_mock(ha_id)
        return ArrayOfPrograms(
            **(
                {
                    "programs": array_of_programs.programs,
                    array_of_programs_program_arg: Program(
                        array_of_programs.programs[0].key, options=options_stages[0]
                    ),
                }
            )
        )

    client.get_all_programs = AsyncMock(side_effect=get_all_programs_with_options_mock)
    setattr(
        client,
        retrieve_options_method,
        AsyncMock(return_value=ArrayOfOptions(options_stages[1])),
    )
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for entity_id, (state, _) in zip(
        option_entity_id.values(), options_state_stage_1, strict=True
    ):
        assert hass.states.is_state(entity_id, state)

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.NOTIFY,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.UNKNOWN,  # Not important
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

    assert getattr(client, retrieve_options_method).called

    for entity_id, (state, _) in zip(
        option_entity_id.values(), options_state_stage_2, strict=True
    ):
        assert hass.states.is_state(entity_id, state)


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
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the option entity handles exceptions correctly."""
    entity_id = "switch.washer_i_dos_1_active"

    client.get_active_program_options = AsyncMock(
        return_value=ArrayOfOptions(
            [Option(OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE, value=True)]
        )
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.NOTIFY,
                data=ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                            raw_key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=ProgramKey.UNKNOWN,  # Not important
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()

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
