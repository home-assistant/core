"""Tests for Shelly media player platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_WALL_DISPLAY
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, patch_platforms

ENTITY_ID = f"{MEDIA_PLAYER_DOMAIN}.test_name"

STATUS_RADIO_STATION = {
    "playback": {
        "enable": True,
        "buffering": False,
        "volume": 5,
        "media_meta": {
            "thumb": "https://www.radio_station.pl/icon.png",
            "title": "Radio Station",
        },
        "media_type": "RADIO",
    },
}
STATUS_AUDIO_FILE = {
    "playback": {
        "buffering": False,
        "enable": True,
        "volume": 2,
        "media_meta": {
            "album": "Album Name",
            "artist": "Artist",
            "duration": 132415,
            "position": 64644,
            "thumb": "data:image/webp;base64,UklGRoQCAABXRUJQVlA4IHgCAACwCgCdASowADAAPpU8mEgloyKhMdmaALASiWI7h6AqwxQigJWENs8WKuSoHSbVjdRTm5ZukgZf/wPRgezI3xOu+YDnyoCbLdHwaUY77je1cTxiGfO5fixiOGFTypQAAP7rJPSYxGEu8aCWwWPgEGga+TD3QYLSPQrmLGEXFc7n1glzPf+crngb69+L3ZQFbEu6TrhOyc4ZmP1KMQ/E25A6fQNT+9FS02EJmDwo4OS7T084Ly3inQn+UgvyQthhK+aeT40bwqS8rToHTi1+xMPkCirZGOaIljQ5LPFx3fRgjaaBShkMOBSSd0Vjtm5pJ74vz6Q+mLwePe5Uy6DfdtWHJhCSwDnyCfIZUuUZ/V7JUGjBMz6Jh8sF5PdYddZQ+sw42v3RC/+Gt4jKVA8wtXhADsAjdOw5WCe/m5KWTE+QC70z96rOu5RBtI/RLHoR8V/3avSFFNAX3p7Ik/IOh+Uhgn0pcbGam5CsL6Jb+giU43fj9p/HnZ0FmybY4rG7B5Z/Sz9KsjhdlkCt65/OJTs90YS+/UkT6uedW3w0DDdlTUlFYBm0PndMDaoqnQWWEd7XtZsdXEgULMFnB1S0dTHfNKHJiau18tIjudt/HP4qhRPD9LXHhKkysXy3SLzvWMQgaXtja6tyDBRnNpYunWrrbBCN/GyuNxod1s6evaCpo3YFDrmXb7INQICV1Oaql8ElYDhLZ3HhouVJlfmE4aYYhlYVfH/yfCf0I0cW3PtRgtrIxF2eP0EkA1Bpw2wYYKnpPQM8V3JcaptgqvO5Oxx3YCV4FjgUA+UiSqoql4VVg3LmqCKbymZMKJHJGkDnjxxSmD0F5BwAAA==",
            "title": "Title",
        },
        "media_type": "AUDIO",
    }
}


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.MEDIA_PLAYER]):
        yield


async def test_rpc_media_player(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a Shelly RPC media player."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_RADIO_STATION
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    assert (state := hass.states.get(ENTITY_ID))
    assert state == snapshot(
        name=f"{ENTITY_ID}-state", exclude=props("entity_picture_local")
    )

    assert (entry := entity_registry.async_get(ENTITY_ID))
    assert entry == snapshot(name=f"{ENTITY_ID}-entry")
