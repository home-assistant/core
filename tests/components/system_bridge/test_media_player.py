"""Tests for the System Bridge media player platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from systembridgeconnector.models.fixtures.modules.media import FIXTURE_MEDIA

from homeassistant.components.media_player import ATTR_MEDIA_POSITION_UPDATED_AT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media player platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_media_position_updated_at(hass: HomeAssistant) -> None:
    """Test the media position updated time is UTC."""
    state = hass.states.get("media_player.hostname_media")
    assert state is not None
    assert state.attributes[
        ATTR_MEDIA_POSITION_UPDATED_AT
    ] == dt_util.utc_from_timestamp(FIXTURE_MEDIA.updated_at)
