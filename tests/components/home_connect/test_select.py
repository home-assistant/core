"""Tests for home_connect select entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfPrograms,
    Event,
    EventKey,
    EventMessage,
    EventType,
    ProgramKey,
)
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import (
    EnumerateProgram,
    EnumerateProgramConstraints,
    Execution,
)
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


async def test_select(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test select entity."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_select_entity_availabilty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test if select entities availability are based on the appliance connection state."""
    entity_ids = [
        "select.washer_active_program",
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
                appliance_ha_id,
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
                appliance_ha_id,
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


async def test_filter_programs(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select that only right programs are shown."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_ECO_50.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_ONLY,
                ),
            ),
            EnumerateProgram(
                key=ProgramKey.UNKNOWN,
                raw_key="an unknown program",
            ),
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_QUICK_45,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_QUICK_45.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.START_ONLY,
                ),
            ),
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_AUTO_1,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_AUTO_1.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            ),
        ]
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get("select.dishwasher_selected_program")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_OPTIONS] == [
        "dishcare_dishwasher_program_eco_50",
        "dishcare_dishwasher_program_auto_1",
    ]

    entity = entity_registry.async_get("select.dishwasher_active_program")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_OPTIONS] == [
        "dishcare_dishwasher_program_quick_45",
        "dishcare_dishwasher_program_auto_1",
    ]


@pytest.mark.parametrize(
    (
        "appliance_ha_id",
        "entity_id",
        "mock_method",
        "program_key",
        "program_to_set",
        "event_key",
    ),
    [
        (
            "Dishwasher",
            "select.dishwasher_selected_program",
            "set_selected_program",
            ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            "dishcare_dishwasher_program_eco_50",
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ),
        (
            "Dishwasher",
            "select.dishwasher_active_program",
            "start_program",
            ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            "dishcare_dishwasher_program_eco_50",
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_select_program_functionality(
    appliance_ha_id: str,
    entity_id: str,
    mock_method: str,
    program_key: ProgramKey,
    program_to_set: str,
    event_key: EventKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test select functionality."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, "unknown")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: program_to_set},
    )
    await hass.async_block_till_done()
    getattr(client, mock_method).assert_awaited_once_with(
        appliance_ha_id, program_key=program_key
    )
    assert hass.states.is_state(entity_id, program_to_set)

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
                            value="A not known program",
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_UNKNOWN)


@pytest.mark.parametrize(
    (
        "entity_id",
        "program_to_set",
        "mock_attr",
        "exception_match",
    ),
    [
        (
            "select.dishwasher_selected_program",
            "dishcare_dishwasher_program_eco_50",
            "set_selected_program",
            r"Error.*select.*program.*",
        ),
        (
            "select.dishwasher_active_program",
            "dishcare_dishwasher_program_eco_50",
            "start_program",
            r"Error.*start.*program.*",
        ),
    ],
)
async def test_select_exception_handling(
    entity_id: str,
    program_to_set: str,
    mock_attr: str,
    exception_match: str,
    hass: HomeAssistant,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test exception handling."""
    client_with_exception.get_all_programs.side_effect = None
    client_with_exception.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_ECO_50.value,
            )
        ]
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        await getattr(client_with_exception, mock_attr)()

    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {"entity_id": entity_id, "option": program_to_set},
            blocking=True,
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2
