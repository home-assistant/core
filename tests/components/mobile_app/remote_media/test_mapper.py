"""The wire contract Core shares with the Home Assistant iOS app.

These assertions are about the encoded JSON, not about Python types. The app decodes it with
Swift `RemoteMediaSessionAttributes`, whose `CodingKeys` name every field below, and two of those
decodes are unconditional — a missing `selection`, `deviceName`, `state` or `features` is a
decoding failure on the device, which looks exactly like a push that never arrived.
"""

from datetime import UTC, datetime
import math
from typing import Any

import pytest

from homeassistant.components.mobile_app.remote_media.mapper import snapshot_from_state
from homeassistant.components.mobile_app.remote_media.model import RemoteMediaSnapshot
from homeassistant.core import HomeAssistant

from .const import ENTITY_ID, PLAYING_ATTRIBUTES, SERVER_ID


def _snapshot(
    hass: HomeAssistant, state: str = "playing", **attributes: Any
) -> RemoteMediaSnapshot | None:
    """Map a media player state through the production mapper."""
    merged = {**PLAYING_ATTRIBUTES, **attributes}
    hass.states.async_set(ENTITY_ID, state, merged)
    return snapshot_from_state(hass.states.get(ENTITY_ID), SERVER_ID)


async def test_wire_keys_are_the_swift_coding_keys(hass: HomeAssistant) -> None:
    """The encoded snapshot uses exactly the names the app decodes."""
    wire = _snapshot(hass).as_wire()
    assert wire == {
        "selection": {"serverId": "home", "entityId": ENTITY_ID},
        "deviceName": "Speaker",
        "state": "playing",
        "features": 84037,
        "title": "First",
        "artist": "Artist",
        "album": "Album",
        "contentId": "track-1",
        "duration": 240.0,
        "position": 10.0,
        "positionUpdatedAtUnix": 1788739200.0,
        "volume": 0.4,
        "isMuted": False,
    }


async def test_required_fields_are_always_present(hass: HomeAssistant) -> None:
    """Swift decodes these unconditionally, so they may never be omitted."""
    wire = _snapshot(
        hass,
        state="idle",
        **dict.fromkeys(
            (
                "media_content_id",
                "media_title",
                "media_artist",
                "media_album_name",
                "media_duration",
                "media_position",
                "media_position_updated_at",
                "volume_level",
                "is_volume_muted",
            )
        ),
    ).as_wire()
    for key in ("selection", "deviceName", "state", "features"):
        assert key in wire, key
    assert wire["selection"] == {"serverId": "home", "entityId": ENTITY_ID}


async def test_position_timestamp_is_unix_seconds(hass: HomeAssistant) -> None:
    """Seconds since 1970, never Swift's 2001 reference epoch.

    The app moved off that deliberately: reproducing `JSONEncoder`'s `Date` encoding from Python
    would be a permanent trap. `2026-09-07T00:00:00+00:00` is 1788739200.
    """
    wire = _snapshot(hass).as_wire()
    assert wire["positionUpdatedAtUnix"] == 1788739200.0
    # The same instant in the reference epoch, which must not be what we wrote.
    assert (
        wire["positionUpdatedAtUnix"] != 810432000.0
    )  # the same instant in Swift 2001 reference epoch
    assert "positionUpdatedAt" not in wire


async def test_nothing_sensitive_reaches_the_wire(hass: HomeAssistant) -> None:
    """The attributes travel through Apple's infrastructure and come back in a push."""
    wire = _snapshot(hass).as_wire()
    encoded = repr(wire)
    assert "entity_picture" not in encoded
    assert "token=secret" not in encoded
    assert "authSig" not in encoded
    assert "bearer" not in encoded.lower()
    assert "authorization" not in encoded.lower()
    # Artwork is not sent at all: the iOS mapper produces none either, and the source path
    # carries a signed token.
    assert "artwork" not in wire


async def test_duration_and_position_are_clamped(hass: HomeAssistant) -> None:
    """Mirrors the Swift mapper: a non-positive duration is no duration."""
    assert _snapshot(hass, media_duration=0).duration is None
    assert _snapshot(hass, media_duration=-5).duration is None
    # Position is held inside the track.
    assert _snapshot(hass, media_position=-3).position == 0.0
    assert _snapshot(hass, media_duration=100, media_position=500).position == 100.0


async def test_position_without_a_timestamp_carries_no_timestamp(
    hass: HomeAssistant,
) -> None:
    """A timestamp with no position would let the card extrapolate from nothing."""
    snapshot = _snapshot(hass, media_position=None)
    assert snapshot.position is None
    assert snapshot.position_updated_at_unix is None


async def test_volume_is_clamped_and_features_are_never_negative(
    hass: HomeAssistant,
) -> None:
    """Integrations do report values outside the documented ranges."""
    assert _snapshot(hass, volume_level=1.5).volume == 1.0
    assert _snapshot(hass, volume_level=-1).volume == 0.0
    assert _snapshot(hass, supported_features=-3).features == 0


async def test_device_name_falls_back_to_the_entity_id(hass: HomeAssistant) -> None:
    """`deviceName` is required, so it always has a value."""
    assert _snapshot(hass, friendly_name=None).device_name == ENTITY_ID


async def test_blank_metadata_is_absent_rather_than_empty(hass: HomeAssistant) -> None:
    """An empty string is not a title; the app treats absence and emptiness differently."""
    snapshot = _snapshot(hass, media_title="", media_artist="")
    assert snapshot.title is None
    assert snapshot.artist is None


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({"media_duration": "240", "media_position": "10"}, (240.0, 10.0)),
        ({"media_duration": "not a number"}, (None, 10.0)),
        ({"media_duration": math.inf}, (None, 10.0)),
        ({"media_duration": True, "media_position": True}, (None, None)),
        ({"media_duration": [240], "media_position": {}}, (None, None)),
    ],
    ids=["numeric strings", "unparsable", "infinite", "booleans", "wrong types"],
)
async def test_numeric_attributes_an_integration_got_wrong(
    hass: HomeAssistant,
    attributes: dict[str, Any],
    expected: tuple[float | None, float | None],
) -> None:
    """Whatever an integration puts in an attribute, the card gets a number or nothing."""
    snapshot = _snapshot(hass, **attributes)
    assert snapshot is not None
    assert (snapshot.duration, snapshot.position) == expected


@pytest.mark.parametrize(
    ("supported_features", "expected"),
    [("84037", 84037), (84037.9, 84037), (True, 0), ("nonsense", 0), (None, 0)],
    ids=["string", "float", "boolean", "unparsable", "missing"],
)
async def test_features_always_reach_the_wire_as_an_integer(
    hass: HomeAssistant, supported_features: Any, expected: int
) -> None:
    """`features` is decoded unconditionally, so it can never be absent or a string."""
    snapshot = _snapshot(hass, supported_features=supported_features)
    assert snapshot is not None
    assert snapshot.features == expected


@pytest.mark.parametrize(
    ("updated_at", "expected"),
    [
        (datetime(2026, 9, 7, tzinfo=UTC), 1788739200.0),
        ("2026-09-07T00:00:00+00:00", 1788739200.0),
        ("halfway through", None),
        (1788480000, None),
        (None, None),
    ],
    ids=["datetime", "string", "unparsable", "bare number", "missing"],
)
async def test_the_position_timestamp_is_unix_seconds_or_absent(
    hass: HomeAssistant, updated_at: Any, expected: float | None
) -> None:
    """A position the card cannot date is better than one it dates wrongly."""
    snapshot = _snapshot(hass, media_position_updated_at=updated_at)
    assert snapshot is not None
    assert snapshot.position_updated_at_unix == expected


async def test_a_muted_flag_that_is_not_a_boolean_is_dropped(
    hass: HomeAssistant,
) -> None:
    """The app decodes `isMuted` as a Bool, so "false" would be a decoding failure."""
    assert _snapshot(hass, is_volume_muted="false").is_muted is None


async def test_only_media_players_are_mapped(hass: HomeAssistant) -> None:
    """A registration can only follow a media player."""
    hass.states.async_set("light.kitchen", "on", {})
    assert snapshot_from_state(hass.states.get("light.kitchen"), SERVER_ID) is None


async def test_track_id_matches_the_swift_construction(hass: HomeAssistant) -> None:
    """Byte-for-byte the Swift `trackId`: each part length-prefixed by its UTF-8 byte count."""
    snapshot = _snapshot(hass)
    assert snapshot.track_id == "7:track-15:First6:Artist5:Album"

    # Absent parts are empty, not skipped, so a shift cannot collide with a different track.
    blank = _snapshot(
        hass, media_content_id=None, media_artist=None, media_album_name=None
    )
    assert blank.track_id == "0:5:First0:0:"

    # A multi-byte title is counted in bytes.
    unicode_title = _snapshot(
        hass,
        media_content_id=None,
        media_title="é",
        media_artist=None,
        media_album_name=None,
    )
    assert unicode_title.track_id == "0:2:é0:0:"


class TestArtwork:
    """Which artwork sources may be handed to a phone, and which may not.

    The extension that renders the card holds no Home Assistant credentials and cannot be given
    any: what goes here is serialized through Apple's infrastructure and echoed back by the push
    relay, so it is effectively public.
    """

    @pytest.mark.parametrize(
        "picture",
        [
            "https://is1-ssl.mzstatic.com/image/thumb/abc/600x600bb.jpg",
            "https://lastfm.freetls.fastly.net/i/u/300x300/abc.png",
        ],
    )
    def test_a_public_absolute_source_is_passed_through(
        self, hass: HomeAssistant, picture: str
    ) -> None:
        """Many integrations expose album art on the service's own CDN. That is fetchable."""
        hass.states.async_set(
            ENTITY_ID, "playing", {**PLAYING_ATTRIBUTES, "entity_picture": picture}
        )
        snapshot = snapshot_from_state(hass.states.get(ENTITY_ID), SERVER_ID)
        assert snapshot.artwork_url == picture
        assert snapshot.as_wire()["artwork"] == {"url": picture}

    @pytest.mark.parametrize(
        ("label", "picture"),
        [
            (
                "a signed proxy path",
                "/api/media_player_proxy/media_player.speaker?token=secret",
            ),
            (
                "a proxy path with no token",
                "/api/media_player_proxy/media_player.speaker",
            ),
            (
                "an absolute proxy URL with a token",
                "https://ha.example.com/api/x?token=secret",
            ),
            ("any query at all", "https://cdn.example.com/art.jpg?sig=abc"),
            ("plain http", "http://cdn.example.com/art.jpg"),
            ("credentials in the authority", "https://user:pw@cdn.example.com/art.jpg"),
            ("no host", "https:///art.jpg"),
            ("not a string", 42),
            ("empty", ""),
        ],
    )
    def test_everything_else_is_withheld(
        self, hass: HomeAssistant, label: str, picture: object
    ) -> None:
        """No token is spent to show a cover, and no phone is sent to a plaintext origin."""
        hass.states.async_set(
            ENTITY_ID, "playing", {**PLAYING_ATTRIBUTES, "entity_picture": picture}
        )
        snapshot = snapshot_from_state(hass.states.get(ENTITY_ID), SERVER_ID)
        assert snapshot.artwork_url is None, label
        assert "artwork" not in snapshot.as_wire(), label

    def test_the_default_fixture_carries_no_artwork(self, hass: HomeAssistant) -> None:
        """`PLAYING_ATTRIBUTES` uses the signed proxy form, which must never cross."""
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        snapshot = snapshot_from_state(hass.states.get(ENTITY_ID), SERVER_ID)
        assert snapshot.artwork_url is None
        assert "token" not in str(snapshot.as_wire())
