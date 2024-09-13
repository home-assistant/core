"""Tests for home_connect select entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import BSH_ACTIVE_PROGRAM
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant

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
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "program_to_set"),
    [
        (
            "select.washer_program",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            SERVICE_SELECT_OPTION,
            bsh_key_to_translation_key(PROGRAM),
        ),
    ],
)
async def test_select_functionality(
    entity_id: str,
    status: dict,
    service: str,
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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(status)
    await hass.services.async_call(
        SELECT_DOMAIN,
        service,
        {"entity_id": entity_id, "option": program_to_set},
        blocking=True,
    )
    assert hass.states.is_state(entity_id, program_to_set)


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "program_to_set", "mock_attr"),
    [
        (
            "select.washer_program",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            SERVICE_SELECT_OPTION,
            bsh_key_to_translation_key(PROGRAM),
            "start_program",
        )
    ],
)
async def test_switch_exception_handling(
    entity_id: str,
    status: dict,
    service: str,
    program_to_set: str,
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
    problematic_appliance.get_programs_available.side_effect = None
    problematic_appliance.get_programs_available.return_value = [PROGRAM]
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    problematic_appliance.status.update(status)
    await hass.services.async_call(
        SELECT_DOMAIN,
        service,
        {"entity_id": entity_id, "option": program_to_set},
        blocking=True,
    )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
