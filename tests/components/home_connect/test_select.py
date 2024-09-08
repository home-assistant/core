"""Tests for home_connect select entities."""

from collections.abc import Awaitable, Callable, Generator
import random
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
)
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant

from .conftest import get_all_appliances

from tests.common import MockConfigEntry

AVAILABLE_PROGRAMS = [
    "LaundryCare.Washer.Program.Cotton",
    "LaundryCare.Washer.Program.Mix",
    "LaundryCare.Washer.Program.Wool",
]


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


async def test_select(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test select entity."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance", ["Cleaning Robot"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "options"),
    [
        (
            "select.cleaning_robot_current_map",
            "ConsumerProducts.CleaningRobot.Setting.CurrentMap",
            (
                "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.TempMap",
                "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map1",
                "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map2",
                "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map3",
            ),
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_select_functionality(
    appliance: Mock,
    entity_id: str,
    setting_key: str,
    options: list[str],
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test select functionality."""
    appliance.get.side_effect = [{ATTR_CONSTRAINTS: {ATTR_ALLOWED_VALUES: options}}]
    get_appliances.return_value = [appliance]
    current_option = random.choice(options)
    option_to_set = random.choice(
        [option for option in options if option != current_option]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update({setting_key: {ATTR_VALUE: current_option}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["options"] == [
        bsh_key_to_translation_key(state) for state in options
    ]
    assert hass.states.is_state(entity_id, bsh_key_to_translation_key(current_option))

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            "option": bsh_key_to_translation_key(option_to_set),
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    appliance.set_setting.assert_called_once_with(setting_key, option_to_set)


@pytest.mark.parametrize("problematic_appliance", ["Cleaning Robot"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "initial_status", "option_to_set", "mock_attr"),
    [
        (
            "select.cleaning_robot_current_map",
            {
                "ConsumerProducts.CleaningRobot.Setting.CurrentMap": {
                    ATTR_VALUE: "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.TempMap",
                }
            },
            "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map2",
            "set_setting",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_select_exception_handling(
    problematic_appliance: Mock,
    entity_id: str,
    initial_status: dict,
    option_to_set: str,
    mock_attr: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test exception handling."""
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    problematic_appliance.status.update(initial_status)
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("entity_id", "available_programs"),
    [
        (
            "select.washer_program",
            AVAILABLE_PROGRAMS,
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_select_program_functionality(
    entity_id: str,
    available_programs: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test select functionality."""
    appliance.get_programs_available.return_value = available_programs
    active_program = random.choice(available_programs)
    program_to_set = random.choice(
        [program for program in available_programs if program != active_program]
    )
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update({BSH_ACTIVE_PROGRAM: {ATTR_VALUE: active_program}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entity_id).attributes["options"] == [
        bsh_key_to_translation_key(program) for program in available_programs
    ]
    assert hass.states.is_state(entity_id, bsh_key_to_translation_key(active_program))

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            "option": bsh_key_to_translation_key(program_to_set),
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    appliance.start_program.assert_called_once_with(program_to_set)


@pytest.mark.parametrize(
    ("entity_id", "status", "available_programs", "mock_attr"),
    [
        (
            "select.washer_program",
            {BSH_ACTIVE_PROGRAM: {ATTR_VALUE: AVAILABLE_PROGRAMS[0]}},
            AVAILABLE_PROGRAMS,
            "start_program",
        )
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_select_program_exception_handling(
    entity_id: str,
    status: dict,
    available_programs: str,
    mock_attr: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    problematic_appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test exception handling."""
    get_appliances.return_value = [problematic_appliance]
    program_to_set = random.choice(available_programs)

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    problematic_appliance.get_programs_available.side_effect = None
    problematic_appliance.get_programs_available.return_value = AVAILABLE_PROGRAMS
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    problematic_appliance.get_programs_available.reset_mock()
    problematic_appliance.get_programs_available.side_effect = HomeConnectError

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    problematic_appliance.status.update(status)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            "option": bsh_key_to_translation_key(program_to_set),
        },
        blocking=True,
    )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
