"""Tests for the Data Grand Lyon calendar platform."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import TclAlert
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.data_grand_lyon.const import TZ_PARIS
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_TCL_ALERTS

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "calendar.line_c3_alerts"


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time inside the in-progress alert of MOCK_TCL_ALERTS."""
    freezer.move_to(datetime(2026, 4, 10, 14, 0, tzinfo=TZ_PARIS))


@pytest.mark.usefixtures("mock_tcl_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_line_config_entry: MockConfigEntry,
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


@pytest.mark.usefixtures("mock_tcl_client")
async def test_state_reflects_alert_in_progress(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
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


async def test_state_on_picks_most_severe_started_alert(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the most severe running alert wins over one that started earlier."""
    mock_tcl_client.get_tcl_alerts.return_value = [
        replace(
            MOCK_TCL_ALERTS[0],
            debut=datetime(2026, 4, 10, 8, 0),
            titre="Earlier minor alert",
            niveau_severite=30,
        ),
        replace(
            MOCK_TCL_ALERTS[0],
            debut=datetime(2026, 4, 10, 9, 0),
            titre="Later severe alert",
            niveau_severite=10,
        ),
    ]
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Later severe alert"


async def test_state_on_prefers_started_alert_over_later_one(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a running alert wins over a more severe one starting later today."""
    ongoing = replace(
        MOCK_TCL_ALERTS[0],
        debut=datetime(2026, 4, 10, 8, 0),
        fin=datetime(2026, 4, 10, 20, 0),
        titre="Ongoing information",
        niveau_severite=30,
    )
    later_today = replace(
        MOCK_TCL_ALERTS[0],
        debut=datetime(2026, 4, 10, 18, 0),
        fin=datetime(2026, 4, 10, 22, 0),
        titre="Later disruption",
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
    ("alerts", "expected_message"),
    [
        pytest.param(
            [
                replace(
                    MOCK_TCL_ALERTS[0],
                    debut=datetime(2026, 4, 10, 18, 0),
                    fin=datetime(2026, 4, 10, 22, 0),
                    titre="Upcoming disruption",
                )
            ],
            "Upcoming disruption",
            id="single_upcoming_alert",
        ),
        pytest.param(
            [
                replace(
                    MOCK_TCL_ALERTS[0],
                    debut=datetime(2026, 4, 10, 16, 0),
                    fin=datetime(2026, 4, 10, 20, 0),
                    titre="Soonest information",
                    niveau_severite=30,
                ),
                replace(
                    MOCK_TCL_ALERTS[0],
                    debut=datetime(2026, 4, 10, 18, 0),
                    fin=datetime(2026, 4, 10, 22, 0),
                    titre="Later severe disruption",
                ),
            ],
            "Soonest information",
            id="soonest_upcoming_alert_wins_over_severity",
        ),
        pytest.param(
            [
                replace(
                    MOCK_TCL_ALERTS[0],
                    debut=datetime(2026, 4, 10, 18, 0),
                    titre="Minor alert",
                    niveau_severite=30,
                ),
                replace(
                    MOCK_TCL_ALERTS[0],
                    debut=datetime(2026, 4, 10, 18, 0),
                    titre="Severe alert",
                    niveau_severite=10,
                ),
            ],
            "Severe alert",
            id="same_start_most_severe_wins",
        ),
    ],
)
async def test_state_off_with_upcoming_alert_picks_soonest(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    alerts: list[TclAlert],
    expected_message: str,
) -> None:
    """Test the event is the soonest upcoming alert, not the most severe one."""
    mock_tcl_client.get_tcl_alerts.return_value = alerts
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == expected_message


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
            # MOCK_TCL_ALERTS[2] spans this window exactly, on line 27.
            datetime(2026, 4, 10, 8, 0, tzinfo=TZ_PARIS),
            datetime(2026, 4, 10, 20, 0, tzinfo=TZ_PARIS),
            ["Déviée dir. Cordeliers"],
            id="excludes_other_lines",
        ),
        pytest.param(
            datetime(2026, 1, 1, 0, 0, tzinfo=TZ_PARIS),
            datetime(2026, 1, 2, 0, 0, tzinfo=TZ_PARIS),
            [],
            id="before_every_alert",
        ),
        pytest.param(
            # MOCK_TCL_ALERTS[0]'s own `fin` as the window start.
            datetime(2026, 4, 30, 17, 30, tzinfo=TZ_PARIS),
            datetime(2026, 5, 1, 0, 0, tzinfo=TZ_PARIS),
            [],
            id="ends_exactly_at_window_start",
        ),
        pytest.param(
            datetime(2026, 3, 15, 0, 0, tzinfo=TZ_PARIS),
            # MOCK_TCL_ALERTS[0]'s own `debut` as the window end.
            datetime(2026, 4, 1, 7, 0, tzinfo=TZ_PARIS),
            [],
            id="starts_exactly_at_window_end",
        ),
    ],
)
@pytest.mark.usefixtures("mock_tcl_client")
async def test_get_events(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
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


@pytest.mark.parametrize(
    ("debut", "fin", "start", "end", "expected"),
    [
        pytest.param(
            datetime(2026, 10, 25, 2, 50),
            datetime(2026, 10, 25, 3, 0),
            datetime(2026, 10, 25, 0, 45, tzinfo=UTC),
            datetime(2026, 10, 25, 1, 15, tzinfo=UTC),
            ["DST alert"],
            id="overlapping_alert_included",
        ),
        pytest.param(
            datetime(2026, 10, 25, 2, 20),
            datetime(2026, 10, 25, 2, 40),
            datetime(2026, 10, 25, 1, 15, tzinfo=UTC),
            datetime(2026, 10, 25, 2, 0, tzinfo=UTC),
            [],
            id="earlier_alert_excluded",
        ),
    ],
)
async def test_get_events_across_dst_rollback(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    debut: datetime,
    fin: datetime,
    start: datetime,
    end: datetime,
    expected: list[str],
) -> None:
    """Test the window is compared in absolute time when Paris falls back an hour."""
    await hass.config.async_set_time_zone("Europe/Paris")
    mock_tcl_client.get_tcl_alerts.return_value = [
        replace(MOCK_TCL_ALERTS[0], debut=debut, fin=fin, titre="DST alert")
    ]
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
    assert summaries == expected
