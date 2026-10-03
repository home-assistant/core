"""Sticky reduction: what the card should show given what integrations actually emit.

Mirrors the cases Swift `RemoteMediaSnapshotReducer` is tested against, because both sides have to
agree. The stake is higher on the server: when an APNs push cold-launches the extension there is
no prior snapshot on the device, so whatever Core sends is the entire card.
"""

import pytest

from homeassistant.components.mobile_app.remote_media.model import RemoteMediaSnapshot
from homeassistant.components.mobile_app.remote_media.reducer import reduce_snapshot

from .const import ENTITY_ID, SERVER_ID


def snapshot(**overrides) -> RemoteMediaSnapshot:
    """A snapshot with playing media, unless overridden."""
    values = {
        "server_id": SERVER_ID,
        "entity_id": ENTITY_ID,
        "device_name": "Speaker",
        "state": "playing",
        "title": "First",
        "artist": "Artist",
        "album": "Album",
        "content_id": "track-1",
        "duration": 240.0,
        "position": 10.0,
        "position_updated_at_unix": 1788739200.0,
        "volume": 0.4,
        "is_muted": False,
        "features": 84037,
    }
    values.update(overrides)
    return RemoteMediaSnapshot(**values)


def blank(state: str) -> RemoteMediaSnapshot:
    """A report with no media at all, as integrations emit between tracks."""
    return RemoteMediaSnapshot(
        server_id=SERVER_ID,
        entity_id=ENTITY_ID,
        device_name="Speaker",
        state=state,
        features=84037,
    )


def test_nothing_to_show_yet() -> None:
    """A blank first report starts no card, and does not end the relationship either."""
    assert reduce_snapshot(None, blank("idle")) is None


def test_a_first_real_track_is_taken_wholesale() -> None:
    """The first meaningful report is the card."""
    incoming = snapshot()
    assert reduce_snapshot(None, incoming) == incoming


def test_paused_retains_its_content() -> None:
    """A paused player still has something to show."""
    reduced = reduce_snapshot(snapshot(), snapshot(state="paused"))
    assert reduced.state == "paused"
    assert reduced.title == "First"


@pytest.mark.parametrize("state", ["idle", "off", "standby"])
def test_idle_with_metadata_keeps_the_media(state: str) -> None:
    """An integration reporting `idle` while still naming a track keeps the track."""
    reduced = reduce_snapshot(snapshot(), snapshot(state=state))
    assert reduced.state == state
    assert reduced.title == "First"
    assert reduced.playback == "stopped"


@pytest.mark.parametrize("state", ["idle", "off", "standby"])
def test_idle_with_blank_metadata_keeps_the_previous_media(state: str) -> None:
    """The wipe is not pushed. On a cold launch it would be the whole card."""
    reduced = reduce_snapshot(snapshot(), blank(state))
    assert reduced.title == "First"
    assert reduced.content_id == "track-1"
    assert reduced.state == state


@pytest.mark.parametrize("state", ["unavailable", "unknown"])
def test_not_reporting_keeps_the_previous_representation(state: str) -> None:
    """`unavailable` means the integration stopped reporting, not that playback stopped.

    An Echo drops off and comes back; showing it as stopped would be inventing a state, and
    ending the session would lose the card for good.
    """
    reduced = reduce_snapshot(snapshot(), blank(state))
    assert reduced.title == "First"
    # The last known playback state is kept rather than replaced with the non-report.
    assert reduced.state == "playing"


def test_a_metadata_hole_is_not_a_new_track() -> None:
    """Pressing Next blanks the metadata for a moment before the next track arrives."""
    previous = snapshot()
    during = reduce_snapshot(previous, blank("playing"))
    assert during.title == "First"
    # And when the real track lands it replaces everything.
    after = reduce_snapshot(during, snapshot(content_id="track-2", title="Second"))
    assert after.title == "Second"
    assert after.content_id == "track-2"


def test_a_new_track_replaces_wholesale() -> None:
    """No part of the previous track's identity survives into a new one."""
    reduced = reduce_snapshot(
        snapshot(),
        snapshot(content_id="track-2", title="Second", artist="Other", album="Later"),
    )
    assert (reduced.title, reduced.artist, reduced.album) == (
        "Second",
        "Other",
        "Later",
    )
    assert reduced.track_id != snapshot().track_id


def test_position_and_volume_do_not_make_a_new_track() -> None:
    """Ordinary progress and a volume nudge are the same track."""
    previous = snapshot()
    moved = reduce_snapshot(previous, snapshot(position=90.0, volume=0.9))
    assert moved.track_id == previous.track_id
    assert moved.position == 90.0
    assert moved.volume == 0.9


def test_stopping_playback_does_not_end_following() -> None:
    """`media_stop` is not Stop Following.

    The reducer never returns "the relationship is over"; it only ever describes a card. Ending is
    a lifecycle decision made elsewhere, from the dismissal webhook.
    """
    for state in ("idle", "off", "paused", "unavailable", "unknown", "standby"):
        assert reduce_snapshot(snapshot(), blank(state)) is not None
