"""Tests for the Duosida EV Charger sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from duosida_ev import ChargerState
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration
from .conftest import CHARGER_STATUS, charger_status

STATUS_ENTITY_ID = "sensor.duosida_ev_charger_status"
SESSION_START_ENTITY_ID = "sensor.duosida_ev_charger_session_start"


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


@pytest.mark.parametrize(
    ("session_start", "expected"),
    [
        pytest.param(None, STATE_UNKNOWN, id="no_session"),
        pytest.param(
            CHARGER_STATUS.session_start,
            "2026-11-07T00:22:00+00:00",
            id="same_session",
        ),
    ],
)
async def test_session_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    session_start: datetime | None,
    expected: str,
) -> None:
    """Test the session start follows the charger, not the time of the push."""
    await setup_integration(hass, mock_config_entry)

    mock_duosida_client.status = charger_status(
        session_start=session_start,
        received_at=CHARGER_STATUS.received_at + timedelta(minutes=30),
    )
    push_update(mock_duosida_client)

    assert hass.states.get(SESSION_START_ENTITY_ID).state == expected
