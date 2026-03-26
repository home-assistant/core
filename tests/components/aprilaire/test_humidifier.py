"""Tests for the Aprilaire humidifier entity."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute

from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierAction,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant


from .conftest import setup_integration
from tests.common import MockConfigEntry

HUMIDIFIER_ENTITY = "humidifier.test_thermostat"
DEHUMIDIFIER_ENTITY = "humidifier.test_thermostat_2"


async def test_humidifier_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test humidifier entity state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["humidity"] == 35
    assert state.attributes["current_humidity"] == 45
    assert state.attributes["action"] == HumidifierAction.HUMIDIFYING
    assert state.attributes["min_humidity"] == 10
    assert state.attributes["max_humidity"] == 50


async def test_dehumidifier_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test dehumidifier entity state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DEHUMIDIFIER_ENTITY)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["humidity"] == 55
    assert state.attributes["action"] == HumidifierAction.DRYING
    assert state.attributes["min_humidity"] == 40
    assert state.attributes["max_humidity"] == 90


async def test_humidifier_auto_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier in auto humidity mode (available=1)."""
    base_coordinator_data[Attribute.HUMIDIFICATION_AVAILABLE] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state is not None
    assert state.attributes["min_humidity"] == 1
    assert state.attributes["max_humidity"] == 7


async def test_humidifier_set_humidity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting humidifier humidity."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: HUMIDIFIER_ENTITY,
            "humidity": 40,
        },
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_called_with(40)


async def test_dehumidifier_set_humidity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting dehumidifier humidity."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: DEHUMIDIFIER_ENTITY,
            "humidity": 50,
        },
        blocking=True,
    )

    mock_client.set_dehumidification_setpoint.assert_called_with(50)


async def test_humidifier_turn_on_with_last_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test turning on humidifier restores last target humidity."""
    await setup_integration(hass, mock_config_entry)

    # First read the state to populate last_target_humidity (35 from fixture)
    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state.state == "on"

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ENTITY},
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_called_with(35)


async def test_humidifier_turn_on_default_humidity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test turning on humidifier uses default when no last target."""
    base_coordinator_data[Attribute.HUMIDIFICATION_SETPOINT] = 0
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ENTITY},
        blocking=True,
    )

    # Default humidity for humidifier is 30
    mock_client.set_humidification_setpoint.assert_called_with(30)


async def test_humidifier_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test turning off humidifier sets humidity to 0."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HUMIDIFIER_ENTITY},
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_called_with(0)


async def test_humidifier_is_off_when_target_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier shows off when target humidity is 0."""
    base_coordinator_data[Attribute.HUMIDIFICATION_SETPOINT] = 0
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state.state == "off"


async def test_humidifier_not_created_when_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier entities aren't created when features unavailable."""
    base_coordinator_data[Attribute.HUMIDIFICATION_AVAILABLE] = 0
    base_coordinator_data[Attribute.DEHUMIDIFICATION_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HUMIDIFIER_ENTITY) is None
    assert hass.states.get(DEHUMIDIFIER_ENTITY) is None


async def test_humidifier_action_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier action idle states."""
    base_coordinator_data[Attribute.HUMIDIFICATION_STATUS] = 0
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state.attributes["action"] == HumidifierAction.IDLE


async def test_humidifier_action_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier action off state."""
    base_coordinator_data[Attribute.HUMIDIFICATION_STATUS] = 3
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HUMIDIFIER_ENTITY)
    assert state.attributes["action"] == HumidifierAction.OFF
