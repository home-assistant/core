"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
    ATTR_KEY,
    ATTR_VALUE,
    BSH_OPERATION_STATE,
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STATE,
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

BSH_CHILD_LOCK_STATE = "BSH.Common.Setting.ChildLock"
SETTINGS_STATUS = {
    setting.pop("key"): setting
    for setting in load_json_object_fixture("home_connect/settings.json")
    .get("Washer")
    .get("data")
    .get("settings")
}


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
    ("entity_id", "setting_key", "setting_value", "status", "service", "state"),
    [
        (
            "switch.washer_power",
            BSH_POWER_STATE,
            BSH_POWER_ON,
            {},
            SERVICE_TURN_ON,
            STATE_ON,
        ),
        (
            "switch.washer_power",
            BSH_POWER_STATE,
            BSH_POWER_OFF,
            {},
            SERVICE_TURN_OFF,
            STATE_OFF,
        ),
        (
            "switch.washer_power",
            BSH_POWER_STATE,
            "",
            {
                BSH_OPERATION_STATE: {
                    ATTR_VALUE: "BSH.Common.EnumType.OperationState.Inactive"
                },
            },
            SERVICE_TURN_OFF,
            STATE_OFF,
        ),
        (
            "switch.washer_child_lock",
            BSH_CHILD_LOCK_STATE,
            True,
            {},
            SERVICE_TURN_ON,
            STATE_ON,
        ),
        (
            "switch.washer_child_lock",
            BSH_CHILD_LOCK_STATE,
            False,
            {},
            SERVICE_TURN_OFF,
            STATE_OFF,
        ),
    ],
)
async def test_switch_functionality(
    entity_id: str,
    setting_key: str,
    setting_value: str,
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
    status.update({setting_key: {ATTR_VALUE: setting_value}})
    appliance.status.update(SETTINGS_STATUS)
    appliance.get = MagicMock(
        return_value={
            ATTR_KEY: BSH_POWER_STATE,
            ATTR_CONSTRAINTS: {ATTR_ALLOWED_VALUES: [BSH_POWER_ON, BSH_POWER_OFF]},
        },
    )
    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update(status)
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, state)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    if setting_key == BSH_POWER_STATE:
        appliance.set_setting.assert_called_once_with(
            setting_key,
            BSH_POWER_ON if service == SERVICE_TURN_ON else BSH_POWER_OFF,
        )
    else:
        appliance.set_setting.assert_called_once_with(
            setting_key,
            service == SERVICE_TURN_ON,
        )


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "mock_attr"),
    [
        (
            "switch.washer_power",
            {BSH_POWER_STATE: {ATTR_VALUE: ""}},
            SERVICE_TURN_ON,
            "set_setting",
        ),
        (
            "switch.washer_power",
            {BSH_POWER_STATE: {ATTR_VALUE: ""}},
            SERVICE_TURN_OFF,
            "set_setting",
        ),
        (
            "switch.washer_child_lock",
            {BSH_CHILD_LOCK_STATE: {ATTR_VALUE: ""}},
            SERVICE_TURN_ON,
            "set_setting",
        ),
        (
            "switch.washer_child_lock",
            {BSH_CHILD_LOCK_STATE: {ATTR_VALUE: ""}},
            SERVICE_TURN_OFF,
            "set_setting",
        ),
    ],
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
    problematic_appliance.status.update(SETTINGS_STATUS)
    problematic_appliance.get = MagicMock(side_effect=HomeConnectError)
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
