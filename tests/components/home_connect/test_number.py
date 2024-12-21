"""Tests for home_connect number entities."""

from collections.abc import Awaitable, Callable, Generator
import random
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import (
    ATTR_CONSTRAINTS,
    ATTR_STEPSIZE,
    ATTR_UNIT,
    ATTR_VALUE,
)
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE as SERVICE_ATTR_VALUE,
    DEFAULT_MIN_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import get_all_appliances

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


async def test_number(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test number entity."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance", ["Refrigerator"], indirect=True)
@pytest.mark.parametrize(
    (
        "entity_id",
        "setting_key",
        "min_value",
        "max_value",
        "step_size",
        "unit_of_measurement",
    ),
    [
        (
            f"{NUMBER_DOMAIN.lower()}.refrigerator_refrigerator_temperature",
            "Refrigeration.FridgeFreezer.Setting.SetpointTemperatureRefrigerator",
            7,
            15,
            0.1,
            "°C",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_number_entity_functionality(
    appliance: Mock,
    entity_id: str,
    setting_key: str,
    bypass_throttle: Generator[None],
    min_value: int,
    max_value: int,
    step_size: float,
    unit_of_measurement: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test number entity functionality."""
    appliance.get.side_effect = [
        {
            ATTR_CONSTRAINTS: {
                ATTR_MIN: min_value,
                ATTR_MAX: max_value,
                ATTR_STEPSIZE: step_size,
            },
            ATTR_UNIT: unit_of_measurement,
        }
    ]
    get_appliances.return_value = [appliance]
    current_value = min_value
    appliance.status.update({setting_key: {ATTR_VALUE: current_value}})

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, str(current_value))
    state = hass.states.get(entity_id)
    assert state.attributes["min"] == min_value
    assert state.attributes["max"] == max_value
    assert state.attributes["step"] == step_size
    assert state.attributes["unit_of_measurement"] == unit_of_measurement

    new_value = random.randint(min_value + 1, max_value)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            SERVICE_ATTR_VALUE: new_value,
        },
        blocking=True,
    )
    appliance.set_setting.assert_called_once_with(setting_key, new_value)


@pytest.mark.parametrize("problematic_appliance", ["Refrigerator"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{NUMBER_DOMAIN.lower()}.refrigerator_refrigerator_temperature",
            "Refrigeration.FridgeFreezer.Setting.SetpointTemperatureRefrigerator",
            "set_setting",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_number_entity_error(
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
    """Test number entity error."""
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    problematic_appliance.status.update({setting_key: {}})
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    with pytest.raises(
        HomeAssistantError, match=r"Error.*assign.*value.*to.*setting.*"
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                SERVICE_ATTR_VALUE: DEFAULT_MIN_VALUE,
            },
            blocking=True,
        )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
