"""Turn a Home Assistant `media_player` state into the iOS wire snapshot.

A deliberate mirror of Swift `RemoteMediaSnapshotMapper`, including its clamping and its rule that
a position without a timestamp is not a position: the app maps the same entity from its own
websocket feed, and a card that disagreed would change appearance depending on whether the phone
happens to be awake.
"""

from datetime import datetime
import math
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.media_player import (
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import State
from homeassistant.util import dt as dt_util

from .model import RemoteMediaSnapshot

MEDIA_PLAYER_PREFIX = "media_player."


def snapshot_from_state(state: State, server_id: str) -> RemoteMediaSnapshot | None:
    """Return the wire snapshot for a media player state, or None if it is not one."""
    if not state.entity_id.startswith(MEDIA_PLAYER_PREFIX):
        return None

    attributes = state.attributes
    # Zero or negative is not a duration; the app drops it so the card shows no scrubber.
    duration = _finite(attributes.get(ATTR_MEDIA_DURATION))
    if duration is not None and duration <= 0:
        duration = None

    position = _finite(attributes.get(ATTR_MEDIA_POSITION))
    if position is not None:
        position = min(duration, max(0.0, position)) if duration else max(0.0, position)

    # Without a position there is nothing for the timestamp to date, and sending one would let the
    # card extrapolate from a value it does not have.
    updated_at = (
        _unix_seconds(attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT))
        if position is not None
        else None
    )

    volume = _finite(attributes.get(ATTR_MEDIA_VOLUME_LEVEL))
    if volume is not None:
        volume = min(1.0, max(0.0, volume))

    features = attributes.get(ATTR_SUPPORTED_FEATURES)
    muted = attributes.get(ATTR_MEDIA_VOLUME_MUTED)

    return RemoteMediaSnapshot(
        artwork_url=_public_artwork(attributes.get(ATTR_ENTITY_PICTURE)),
        server_id=server_id,
        entity_id=state.entity_id,
        device_name=_non_empty(attributes.get(ATTR_FRIENDLY_NAME)) or state.entity_id,
        state=state.state,
        device_class=_non_empty(attributes.get(ATTR_DEVICE_CLASS)),
        title=_non_empty(attributes.get(ATTR_MEDIA_TITLE)),
        artist=_non_empty(attributes.get(ATTR_MEDIA_ARTIST)),
        album=_non_empty(attributes.get(ATTR_MEDIA_ALBUM_NAME)),
        content_id=_non_empty(attributes.get(ATTR_MEDIA_CONTENT_ID)),
        duration=duration,
        position=position,
        position_updated_at_unix=updated_at,
        volume=volume,
        is_muted=muted if isinstance(muted, bool) else None,
        features=max(0, _int(features) or 0),
    )


def _public_artwork(value: Any) -> str | None:
    """Return an artwork source the phone may fetch with no credentials, or None.

    This value is serialized through Apple's infrastructure and echoed back by the push relay, so
    whatever is put here is effectively public. An absolute HTTPS URL with no query and no userinfo
    — how most integrations expose album art on the service's own CDN — is passed through; anything
    else is refused, because a `/api/media_player_proxy/...` path carries a signed token, and the
    phone showing no artwork is better than giving that away.
    """
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        # Relative paths are Home Assistant's own proxy, and plain HTTP is not somewhere to send a
        # phone that may be on any network.
        return None
    if parsed.username or parsed.password:
        return None
    if not parsed.hostname:
        return None
    if parsed.query:
        # Where the signed token lives. A source that needs one is not a public reference.
        return None
    return value


def _finite(value: Any) -> float | None:
    """Return a usable float, or None. Mirrors the Swift mapper's `finite`."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
    elif isinstance(value, str):
        try:
            candidate = float(value)
        except ValueError:
            return None
    else:
        return None
    return candidate if math.isfinite(candidate) else None


def _int(value: Any) -> int | None:
    """Return a usable int, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _non_empty(value: Any) -> str | None:
    """Return a non-empty string, or None."""
    return value if isinstance(value, str) and value else None


def _unix_seconds(value: Any) -> float | None:
    """Return seconds since 1970 for a Home Assistant timestamp attribute.

    Never Swift's 2001 reference epoch: the app decodes Unix seconds so that Core does not have to
    reproduce `JSONEncoder`'s `Date` encoding.
    """
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        return parsed.timestamp() if parsed else None
    return None
