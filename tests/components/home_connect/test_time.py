"""Tests for home_connect time entities."""

from collections.abc import Awaitable, Callable, Generator
from datetime import time
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import ATTR_VALUE
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import get_all_appliances

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TIME]


async def test_time(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test time entity."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "setting_value", "expected_state"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
            {ATTR_VALUE: 59},
            str(time(second=59)),
        ),
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
            {ATTR_VALUE: None},
            "unknown",
        ),
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
            None,
            "unknown",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_time_entity_functionality(
    appliance: Mock,
    entity_id: str,
    setting_key: str,
    setting_value: dict,
    expected_state: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test time entity functionality."""
    get_appliances.return_value = [appliance]
    appliance.status.update({setting_key: setting_value})

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, expected_state)

    new_value = 30
    assert hass.states.get(entity_id).state != new_value
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(second=new_value),
        },
        blocking=True,
    )
    appliance.set_setting.assert_called_once_with(setting_key, new_value)


@pytest.mark.parametrize("problematic_appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
            "set_setting",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_time_entity_error(
    problematic_appliance: Mock,
    entity_id: str,
    setting_key: str,
    mock_attr: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test time entity error."""
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    problematic_appliance.status.update({setting_key: {}})
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    with pytest.raises(
        ServiceValidationError, match=r"Error.*assign.*value.*to.*setting.*"
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TIME: time(minute=1),
            },
            blocking=True,
        )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
