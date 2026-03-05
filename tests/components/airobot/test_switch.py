"""Tests for the Airobot switch platform."""

from unittest.mock import AsyncMock

from pyairobotrest.exceptions import AirobotError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "method_name"),
    [
        ("switch.test_thermostat_child_lock", "set_child_lock"),
        (
            "switch.test_thermostat_actuator_exercise_disabled",
            "toggle_actuator_exercise",
        ),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    entity_id: str,
    method_name: str,
) -> None:
    """Test switch turn on/off functionality."""
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    mock_method = getattr(mock_airobot_client, method_name)

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_method.assert_called_once_with(True)
    mock_method.reset_mock()

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_method.assert_called_once_with(False)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switch_state_updates(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_settings,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that switch state updates when coordinator refreshes."""
    # Initial state - both switches off
    child_lock = hass.states.get("switch.test_thermostat_child_lock")
    assert child_lock is not None
    assert child_lock.state == STATE_OFF

    actuator_disabled = hass.states.get(
        "switch.test_thermostat_actuator_exercise_disabled"
    )
    assert actuator_disabled is not None
    assert actuator_disabled.state == STATE_OFF

    # Update settings to enable both
    mock_settings.setting_flags.childlock_enabled = True
    mock_settings.setting_flags.actuator_exercise_disabled = True
    mock_airobot_client.get_settings.return_value = mock_settings

    # Trigger coordinator update
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    # Verify states updated
    child_lock = hass.states.get("switch.test_thermostat_child_lock")
    assert child_lock is not None
    assert child_lock.state == STATE_ON

    actuator_disabled = hass.states.get(
        "switch.test_thermostat_actuator_exercise_disabled"
    )
    assert actuator_disabled is not None
    assert actuator_disabled.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "method_name", "service", "expected_key"),
    [
        (
            "switch.test_thermostat_child_lock",
            "set_child_lock",
            SERVICE_TURN_ON,
            "child_lock",
        ),
        (
            "switch.test_thermostat_child_lock",
            "set_child_lock",
            SERVICE_TURN_OFF,
            "child_lock",
        ),
        (
            "switch.test_thermostat_actuator_exercise_disabled",
            "toggle_actuator_exercise",
            SERVICE_TURN_ON,
            "actuator_exercise_disabled",
        ),
        (
            "switch.test_thermostat_actuator_exercise_disabled",
            "toggle_actuator_exercise",
            SERVICE_TURN_OFF,
            "actuator_exercise_disabled",
        ),
    ],
)
async def test_switch_error_handling(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    entity_id: str,
    method_name: str,
    service: str,
    expected_key: str,
) -> None:
    """Test switch error handling for turn on/off operations."""
    mock_method = getattr(mock_airobot_client, method_name)
    mock_method.side_effect = AirobotError("Test error")

    with pytest.raises(HomeAssistantError, match=expected_key):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    expected_value = service == SERVICE_TURN_ON
    mock_method.assert_called_once_with(expected_value)
