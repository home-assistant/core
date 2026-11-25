"""Tests for the Bambu Lab sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiobambulab import PrintState
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

PRINT_STATUS = "sensor.x1_carbon_print_status"
PRINT_FINISH = "sensor.x1_carbon_print_finish"


@pytest.mark.freeze_time("2026-11-15 12:00:00+00:00")
@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors of a printer."""
    with patch("homeassistant.components.bambu_lab._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_chamber_temperature(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a printer without chamber sensor has no sensor for it."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, chamber_temperature=None
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.x1_carbon_bed_temperature") is not None
    assert hass.states.get("sensor.x1_carbon_chamber_temperature") is None


async def test_update(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors follow what the printer pushes."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state,
        print_state=PrintState.PAUSED,
        progress=43,
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == "paused"
    assert hass.states.get("sensor.x1_carbon_print_progress").state == "43"


async def test_print_finish(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the moment the print finishes only moves when the estimate changes."""
    freezer.move_to("2026-11-15 12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PRINT_FINISH).state == "2026-11-15T13:13:00+00:00"

    # The printer rounds to minutes, and its clock is not ours.
    freezer.tick(timedelta(seconds=90))
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_FINISH).state == "2026-11-15T13:13:00+00:00"

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, remaining_minutes=80
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_FINISH).state == "2026-11-15T13:21:30+00:00"


async def test_print_finish_of_next_print(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new print does not report the moment the previous one finished."""
    freezer.move_to("2026-11-15 12:00:00+00:00")
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, remaining_minutes=1
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PRINT_FINISH).state == "2026-11-15T12:01:00+00:00"

    printing = mock_bambu_lab_client.state
    mock_bambu_lab_client.state = replace(
        printing, print_state=PrintState.FINISHED, remaining_minutes=0
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_FINISH).state == STATE_UNKNOWN

    # A minute later a print of one minute starts: within the ignored variance
    # of the previous estimate.
    freezer.tick(timedelta(seconds=90))
    mock_bambu_lab_client.state = printing
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_FINISH).state == "2026-11-15T12:02:30+00:00"


@pytest.mark.parametrize(
    "changes",
    [
        {"remaining_minutes": None},
        {"print_state": PrintState.FINISHED, "remaining_minutes": 0},
        {"print_state": PrintState.IDLE},
    ],
    ids=["no_estimate", "finished", "idle"],
)
async def test_print_finish_unknown(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    changes: dict[str, PrintState | int | None],
) -> None:
    """Test there is no moment the print finishes without a print in progress."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.state = replace(mock_bambu_lab_client.state, **changes)
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_FINISH).state == STATE_UNKNOWN


async def test_unavailable(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors are unavailable while the printer is not connected."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.available = False
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == STATE_UNAVAILABLE

    mock_bambu_lab_client.available = True
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_STATUS).state == "printing"
