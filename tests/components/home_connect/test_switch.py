"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectAppliance, HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    BSH_ACTIVE_PROGRAM,
    BSH_CHILD_LOCK_STATE,
    BSH_OPERATION_STATE,
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STATE,
    REFRIGERATION_SUPERMODEFREEZER,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from .conftest import get_all_appliances

from tests.common import MockConfigEntry, load_json_object_fixture

SETTINGS_STATUS = {
    setting.pop("key"): setting
    for setting in load_json_object_fixture("home_connect/settings.json")
    .get("Dishwasher")
    .get("data")
    .get("settings")
}

PROGRAM = "LaundryCare.Dryer.Program.Mix"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


async def test_switches(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test switch entities."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "state", "appliance"),
    [
        (
            "switch.dishwasher_program_mix",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            SERVICE_TURN_ON,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_program_mix",
            {BSH_ACTIVE_PROGRAM: {"value": ""}},
            SERVICE_TURN_OFF,
            STATE_OFF,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            {BSH_POWER_STATE: {"value": BSH_POWER_ON}},
            SERVICE_TURN_ON,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            {BSH_POWER_STATE: {"value": BSH_POWER_OFF}},
            SERVICE_TURN_OFF,
            STATE_OFF,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            {
                BSH_POWER_STATE: {"value": ""},
                BSH_OPERATION_STATE: {
                    "value": "BSH.Common.EnumType.OperationState.Inactive"
                },
            },
            SERVICE_TURN_OFF,
            STATE_OFF,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_child_lock",
            {BSH_CHILD_LOCK_STATE: {"value": True}},
            SERVICE_TURN_ON,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_child_lock",
            {BSH_CHILD_LOCK_STATE: {"value": False}},
            SERVICE_TURN_OFF,
            STATE_OFF,
            "Dishwasher",
        ),
    ],
    indirect=["appliance"],
)
async def test_switch_functionality(
    entity_id: str,
    status: dict,
    service: str,
    state: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test switch functionality."""
    appliance.status.update(SETTINGS_STATUS)
    appliance.get_programs_available.return_value = [PROGRAM]
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(status)
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "mock_attr", "problematic_appliance"),
    [
        (
            "switch.dishwasher_program_mix",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            SERVICE_TURN_ON,
            "start_program",
            "Dishwasher",
        ),
        (
            "switch.dishwasher_program_mix",
            {BSH_ACTIVE_PROGRAM: {"value": PROGRAM}},
            SERVICE_TURN_OFF,
            "stop_program",
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            {BSH_POWER_STATE: {"value": ""}},
            SERVICE_TURN_ON,
            "set_setting",
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            {BSH_POWER_STATE: {"value": ""}},
            SERVICE_TURN_OFF,
            "set_setting",
            "Dishwasher",
        ),
        (
            "switch.dishwasher_child_lock",
            {BSH_CHILD_LOCK_STATE: {"value": ""}},
            SERVICE_TURN_ON,
            "set_setting",
            "Dishwasher",
        ),
        (
            "switch.dishwasher_child_lock",
            {BSH_CHILD_LOCK_STATE: {"value": ""}},
            SERVICE_TURN_OFF,
            "set_setting",
            "Dishwasher",
        ),
    ],
    indirect=["problematic_appliance"],
)
async def test_switch_exception_handling(
    entity_id: str,
    status: dict,
    service: str,
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
    problematic_appliance.status.update(status)
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {"entity_id": entity_id}, blocking=True
    )
    assert getattr(problematic_appliance, mock_attr).call_count == 2


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "state", "appliance"),
    [
        (
            "switch.fridgefreezer_freezer_super_mode",
            {REFRIGERATION_SUPERMODEFREEZER: {"value": True}},
            SERVICE_TURN_ON,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "switch.fridgefreezer_freezer_super_mode",
            {REFRIGERATION_SUPERMODEFREEZER: {"value": False}},
            SERVICE_TURN_OFF,
            STATE_OFF,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
async def test_ent_desc_switch_functionality(
    entity_id: str,
    status: dict,
    service: str,
    state: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test switch functionality - entity description setup."""
    appliance.status.update(
        HomeConnectAppliance.json2dict(
            load_json_object_fixture("home_connect/settings.json")
            .get(appliance.name)
            .get("data")
            .get("settings")
        )
    )
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(status)
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "mock_attr", "problematic_appliance"),
    [
        (
            "switch.fridgefreezer_freezer_super_mode",
            {REFRIGERATION_SUPERMODEFREEZER: {"value": ""}},
            SERVICE_TURN_ON,
            "set_setting",
            "FridgeFreezer",
        ),
        (
            "switch.fridgefreezer_freezer_super_mode",
            {REFRIGERATION_SUPERMODEFREEZER: {"value": ""}},
            SERVICE_TURN_OFF,
            "set_setting",
            "FridgeFreezer",
        ),
    ],
    indirect=["problematic_appliance"],
)
async def test_ent_desc_switch_exception_handling(
    entity_id: str,
    status: dict,
    service: str,
    mock_attr: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    problematic_appliance: Mock,
    get_appliances: MagicMock,
) -> None:
    """Test switch exception handling - entity description setup."""
    problematic_appliance.status.update(
        HomeConnectAppliance.json2dict(
            load_json_object_fixture("home_connect/settings.json")
            .get(problematic_appliance.name)
            .get("data")
            .get("settings")
        )
    )
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    problematic_appliance.status.update(status)
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
