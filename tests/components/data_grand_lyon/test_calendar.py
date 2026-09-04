"""Tests for the Data Grand Lyon calendar platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import TclAlert, TclAlertSeverityType, TclAlertType
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.data_grand_lyon.const import TZ_PARIS
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_TCL_ALERTS

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "calendar.line_c3"


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time inside the in-progress alert of MOCK_TCL_ALERTS."""
    freezer.move_to(datetime(2026, 4, 10, 14, 0, tzinfo=TZ_PARIS))


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test all calendar entities (state, attributes, registry)."""
    with patch(
        "homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.CALENDAR]
    ):
        mock_line_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_line_config_entry.entry_id
    )


async def test_state_reflects_alert_in_progress(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the calendar is on while an alert is in progress."""
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Déviée dir. Cordeliers"
    assert "Cause: travaux" in state.attributes["description"]


async def test_state_off_without_alert(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a line with no alert is available and off."""
    mock_tcl_client.get_tcl_alerts.return_value = []
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_off_when_every_alert_has_ended(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a line whose only alert has already ended is off."""
    mock_tcl_client.get_tcl_alerts.return_value = [MOCK_TCL_ALERTS[1]]
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_on_prefers_started_alert_over_later_one(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test an alert already running is preferred over one starting later today.

    Both alerts share the library's relevance bucket (an alert starting later
    today counts as CURRENT too), and within that bucket the lower-severity
    (more disruptive) alert would normally sort first. If the entity naively
    took that top-ranked alert, it would report an alert starting at 18:00 as
    the event at 14:00, and HA would compute the on/off state as off despite
    the ongoing alert.
    """
    ongoing = TclAlert(
        type=TclAlertType.INFORMATION,
        cause="événement",
        debut=datetime(2026, 4, 10, 8, 0),
        fin=datetime(2026, 4, 10, 20, 0),
        mode="Bus",
        ligne_com="C3",
        ligne_cli="C3",
        titre="Ongoing information",
        message="Service normal, information seulement.",
        last_update_fme=datetime(2026, 4, 10, 9, 15),
        n=10,
        type_severite=TclAlertSeverityType.OTHER_EFFECT,
        niveau_severite=30,
        type_objet="line",
        liste_objet="C3",
    )
    later_today = TclAlert(
        type=TclAlertType.DISRUPTION,
        cause="travaux",
        debut=datetime(2026, 4, 10, 18, 0),
        fin=datetime(2026, 4, 10, 22, 0),
        mode="Bus",
        ligne_com="C3",
        ligne_cli="C3",
        titre="Later disruption",
        message="Déviation à partir de 18h.",
        last_update_fme=datetime(2026, 4, 10, 9, 15),
        n=11,
        type_severite=TclAlertSeverityType.SIGNIFICANT_DELAYS,
        niveau_severite=20,
        type_objet="line",
        liste_objet="C3",
    )
    mock_tcl_client.get_tcl_alerts.return_value = [ongoing, later_today]
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Ongoing information"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        pytest.param(
            datetime(2026, 4, 9, 0, 0, tzinfo=TZ_PARIS),
            datetime(2026, 4, 11, 0, 0, tzinfo=TZ_PARIS),
            ["Déviée dir. Cordeliers"],
            id="inside_ongoing_alert",
        ),
        pytest.param(
            datetime(2026, 2, 1, 0, 0, tzinfo=TZ_PARIS),
            datetime(2026, 5, 1, 0, 0, tzinfo=TZ_PARIS),
            ["Déviée dir. Cordeliers", "Fête de la Musique"],
            id="spans_both_alerts",
        ),
        pytest.param(
            datetime(2026, 1, 1, 0, 0, tzinfo=TZ_PARIS),
            datetime(2026, 1, 2, 0, 0, tzinfo=TZ_PARIS),
            [],
            id="before_every_alert",
        ),
    ],
)
async def test_get_events(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    start: datetime,
    end: datetime,
    expected: list[str],
) -> None:
    """Test the requested window selects the overlapping alerts."""
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": ENTITY_ID,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        },
        blocking=True,
        return_response=True,
    )
    summaries = [event["summary"] for event in response[ENTITY_ID]["events"]]
    assert sorted(summaries) == sorted(expected)
