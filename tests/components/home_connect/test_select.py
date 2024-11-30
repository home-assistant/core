"""Tests for home_connect select entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    BSH_ACTIVE_PROGRAM,
    BSH_SELECTED_PROGRAM,
)
from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import get_all_appliances

from tests.common import MockConfigEntry, load_json_object_fixture

SETTINGS_STATUS = {
    setting.pop("key"): setting
    for setting in load_json_object_fixture("home_connect/settings.json")
    .get("Washer")
    .get("data")
    .get("settings")
}

PROGRAM = "Dishcare.Dishwasher.Program.Eco50"


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
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("entity_id", "status", "program_to_set"),
    [
        (
            "select.washer_selected_program",
            {BSH_SELECTED_PROGRAM: {"value": PROGRAM}},
            "dishcare_dishwasher_program_eco_50",
        ),
        (
            "select.washer_active_program",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            "dishcare_dishwasher_program_eco_50",
        ),
    ],
)
async def test_select_functionality(
    entity_id: str,
    status: dict,
    program_to_set: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test select functionality."""
    appliance.status.update(SETTINGS_STATUS)
    appliance.get_programs_available.return_value = [PROGRAM]
    get_appliances.return_value = [appliance]

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    appliance.status.update(status)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: program_to_set},
        blocking=True,
    )
    assert hass.states.is_state(entity_id, program_to_set)


@pytest.mark.parametrize(
    (
        "entity_id",
        "status",
        "program_to_set",
        "mock_attr",
        "exception_match",
    ),
    [
        (
            "select.washer_selected_program",
            {BSH_SELECTED_PROGRAM: {"value": PROGRAM}},
            "dishcare_dishwasher_program_eco_50",
            "select_program",
            r"Error.*select.*program.*",
        ),
        (
            "select.washer_active_program",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            "dishcare_dishwasher_program_eco_50",
            "start_program",
            r"Error.*start.*program.*",
        ),
    ],
)
async def test_select_exception_handling(
    entity_id: str,
    status: dict,
    program_to_set: str,
    mock_attr: str,
    exception_match: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    problematic_appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test exception handling."""
    problematic_appliance.get_programs_available.side_effect = None
    problematic_appliance.get_programs_available.return_value = [PROGRAM]
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    problematic_appliance.status.update(status)
    with pytest.raises(ServiceValidationError, match=exception_match):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {"entity_id": entity_id, "option": program_to_set},
            blocking=True,
        )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
