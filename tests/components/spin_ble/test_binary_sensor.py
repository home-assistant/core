"""Tests for the Spin EV Charger binary sensors."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from spinev_ble import ChargerState
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import IDLE_STATUS

PLUG_SENSOR = "binary_sensor.123456789012_plug"
PROBLEM_SENSOR = "binary_sensor.123456789012_problem"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Set up only the binary sensor platform."""
    with patch("homeassistant.components.spin_ble.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("mock_charger")
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The binary sensor platform registers the entities it is expected to."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param(ChargerState.AVAILABLE, STATE_OFF, id="available"),
        # The charger cannot tell whether a vehicle is plugged in while it
        # starts up or is out of service.
        pytest.param(ChargerState.BOOTING, STATE_OFF, id="booting"),
        pytest.param(ChargerState.UNAVAILABLE, STATE_OFF, id="out_of_service"),
        pytest.param(ChargerState.IDLE, STATE_ON, id="idle"),
        pytest.param(ChargerState.CHARGING, STATE_ON, id="charging"),
        pytest.param(ChargerState.EV_SUSPENDED, STATE_ON, id="ev_suspended"),
        pytest.param(ChargerState.FINISHING, STATE_ON, id="finishing"),
        pytest.param(ChargerState.FAULT, STATE_ON, id="fault"),
        pytest.param(None, STATE_UNKNOWN, id="unrecognised"),
    ],
)
async def test_plug_follows_the_charger_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    state: ChargerState | None,
    expected: str,
) -> None:
    """The plug sensor is on whenever the charger reports a vehicle."""
    mock_charger.async_get_status.return_value = replace(IDLE_STATUS, state=state)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PLUG_SENSOR).state == expected


@pytest.mark.parametrize(
    ("alarms", "expected"),
    [
        pytest.param((), STATE_OFF, id="no_alarms"),
        pytest.param(("Mains Low",), STATE_ON, id="one_alarm"),
        pytest.param(("Mains Low", "Earth Wire Open"), STATE_ON, id="two_alarms"),
    ],
)
async def test_problem_follows_the_alarms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    alarms: tuple[str, ...],
    expected: str,
) -> None:
    """The problem sensor is on while the charger reports any alarm."""
    mock_charger.async_get_status.return_value = replace(IDLE_STATUS, alarms=alarms)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PROBLEM_SENSOR).state == expected
