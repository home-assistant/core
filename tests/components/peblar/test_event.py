"""Tests for the Peblar event platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from peblar import PeblarMeterHistory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "event.peblar_ev_charger_session_authorization"


def _history(session_number: int, auth_token: str | None) -> PeblarMeterHistory:
    """Return a history holding one session, authorized with this token."""
    return PeblarMeterHistory.from_dict(
        {
            "Corrupted": False,
            "CorruptedSession": [False],
            "Session": [
                {
                    "AuthToken": auth_token,
                    "Checksum": 3405691582,
                    "SessionNumber": session_number,
                    "SessionStartEnergymWh": 96000000,
                    "SessionStartTime": 1756540800,
                }
            ],
        }
    )


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the authorization coordinator run one poll."""
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the event entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_session_already_running_is_not_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the session in progress at startup does not fire an event.

    It was authorized before anyone here was watching, and stamping it
    with the time it was noticed would put the wrong time on it. The poll
    matters here: setting up happens before the entity exists, so the
    first chance to get this wrong is the poll that follows.
    """
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    await _async_poll(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_only_the_recent_past_is_asked_for(mock_peblar: MagicMock) -> None:
    """Test the charger is asked for a window, not for everything it has.

    Without a bound it hands back its entire history, which on a charger
    in daily use is tens of times larger than what is needed here.
    """
    start = mock_peblar.meter_history.call_args.kwargs["start"]

    assert start is not None
    assert timedelta(days=6) < dt_util.utcnow() - start < timedelta(days=8)


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_new_session_names_who_started_it(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a card shown to the charger reports who it belongs to.

    The card is what an automation acts on, so it comes along by the name
    someone gave it rather than by the identifier on the card itself.
    """
    mock_peblar.meter_history.return_value = _history(43, "1D0A0B0C0D0E03")
    await _async_poll(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNKNOWN
    assert state.attributes["event_type"] == "session_authorized"
    assert state.attributes["token"] == "Frenck"
    assert state.attributes["session_number"] == 43
    assert state.attributes["started_at"] == "2025-08-30T08:00:00+00:00"
    assert "1D0A0B0C0D0E03" not in str(state.attributes)


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_the_same_session_is_only_reported_once(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session that is still running does not report again.

    Every poll hands back the session the charger is on, so without
    looking at which session it is, a car left plugged in overnight would
    report being authorized every five minutes.
    """
    mock_peblar.meter_history.return_value = _history(43, "1D0A0B0C0D0E03")
    await _async_poll(hass, freezer)

    first = hass.states.get(ENTITY_ID).state

    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == first


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_the_same_card_twice_is_reported_twice(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test charging twice on one card reports both times.

    This is what a state cannot do: the name does not change between the
    two, so anything watching for a change would miss the second.
    """
    mock_peblar.meter_history.return_value = _history(43, "1D0A0B0C0D0E03")
    await _async_poll(hass, freezer)
    first = hass.states.get(ENTITY_ID).state

    mock_peblar.meter_history.return_value = _history(44, "1D0A0B0C0D0E03")
    await _async_poll(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != first
    assert state.attributes["token"] == "Frenck"
    assert state.attributes["session_number"] == 44


@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "history",
    [
        PeblarMeterHistory(corrupted=False, corrupted_session=[], session=[]),
        _history(43, None),
        _history(43, "0000000000FFFF"),
    ],
    ids=["nothing charged in the window", "charged without a card", "card deleted"],
)
async def test_nothing_to_report(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
    history: PeblarMeterHistory,
) -> None:
    """Test a session nobody was shown in for stays quiet.

    A charger set to charge without authentication was shown no card, a
    quiet charger has no session to point at, and a card deleted since
    has no name left to give.
    """
    mock_peblar.meter_history.return_value = history
    await _async_poll(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("mock_peblar", [{"HwHasRfid": False}], indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.EVENT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_no_reader_no_entity(hass: HomeAssistant) -> None:
    """Test a charger without a reader shows nobody in."""
    assert hass.states.get(ENTITY_ID) is None
