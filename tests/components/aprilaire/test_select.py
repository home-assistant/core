"""Tests for the Aprilaire select entity."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry

AIR_CLEANING_EVENT = "select.test_thermostat"
AIR_CLEANING_MODE = "select.test_thermostat_2"
FRESH_AIR_EVENT = "select.test_thermostat_3"
FRESH_AIR_MODE = "select.test_thermostat_4"


async def test_air_cleaning_event_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test air cleaning event select state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AIR_CLEANING_EVENT)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["options"] == ["off", "event_clean", "allergies"]


async def test_air_cleaning_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test air cleaning mode select state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AIR_CLEANING_MODE)
    assert state is not None
    assert state.state == "constant_clean"
    assert state.attributes["options"] == ["off", "constant_clean", "automatic"]


async def test_fresh_air_event_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test fresh air event select state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRESH_AIR_EVENT)
    assert state is not None
    assert state.state == "off"


async def test_fresh_air_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test fresh air mode select state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRESH_AIR_MODE)
    assert state is not None
    assert state.state == "automatic"
    assert state.attributes["options"] == ["off", "automatic"]


async def test_select_air_cleaning_event_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test selecting an air cleaning event option."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: AIR_CLEANING_EVENT,
            "option": "allergies",
        },
        blocking=True,
    )

    # event_value=4 (allergies), mode_value=1 (current mode from data)
    mock_client.set_air_cleaning.assert_called_once_with(1, 4)


async def test_select_air_cleaning_mode_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test selecting an air cleaning mode option."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: AIR_CLEANING_MODE,
            "option": "automatic",
        },
        blocking=True,
    )

    # mode_value=2 (automatic), event_value=0 (current event from data)
    mock_client.set_air_cleaning.assert_called_once_with(2, 0)


async def test_select_fresh_air_event_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test selecting a fresh air event option."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: FRESH_AIR_EVENT,
            "option": "3hour",
        },
        blocking=True,
    )

    # event_value=2 (3hour), mode_value=1 (current mode from data)
    mock_client.set_fresh_air.assert_called_once_with(1, 2)


async def test_select_fresh_air_mode_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test selecting a fresh air mode option."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: FRESH_AIR_MODE,
            "option": "off",
        },
        blocking=True,
    )

    # mode_value=0 (off), event_value=0 (current event from data)
    mock_client.set_fresh_air.assert_called_once_with(0, 0)


async def test_select_not_created_when_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test select entities aren't created when features unavailable."""
    base_coordinator_data[Attribute.AIR_CLEANING_AVAILABLE] = 0
    base_coordinator_data[Attribute.VENTILATION_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(AIR_CLEANING_EVENT) is None
    assert hass.states.get(AIR_CLEANING_MODE) is None
    assert hass.states.get(FRESH_AIR_EVENT) is None
    assert hass.states.get(FRESH_AIR_MODE) is None


async def test_select_current_option_with_active_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test select shows correct current option when event is active."""
    base_coordinator_data[Attribute.AIR_CLEANING_EVENT] = 3
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AIR_CLEANING_EVENT)
    assert state.state == "event_clean"
