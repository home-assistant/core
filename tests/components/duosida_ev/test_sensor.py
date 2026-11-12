"""Tests for the Duosida EV Charger sensors."""

from unittest.mock import MagicMock

from duosida_ev import ChargerState
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration
from .conftest import charger_status

STATUS_ENTITY_ID = "sensor.duosida_ev_charger_status"
SESSION_TIME_ENTITY_ID = "sensor.duosida_ev_charger_session_time"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_duosida_client")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param(ChargerState.AVAILABLE, "available", id="available"),
        pytest.param(ChargerState.SUSPENDED_EV, "suspended_ev", id="suspended_ev"),
        pytest.param(ChargerState.UNAVAILABLE, "inoperative", id="inoperative"),
        pytest.param(ChargerState.UNKNOWN, STATE_UNKNOWN, id="unknown_code"),
    ],
)
async def test_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    state: ChargerState,
    expected: str,
) -> None:
    """Test the charger state maps to the status options."""
    await setup_integration(hass, mock_config_entry)

    mock_duosida_client.status = charger_status(state=state)
    push_update(mock_duosida_client)

    assert hass.states.get(STATUS_ENTITY_ID).state == expected


async def test_session_time_without_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
) -> None:
    """Test the session time is unknown while there is no session."""
    await setup_integration(hass, mock_config_entry)

    mock_duosida_client.status = charger_status(session_start=None)
    push_update(mock_duosida_client)

    assert hass.states.get(SESSION_TIME_ENTITY_ID).state == STATE_UNKNOWN
