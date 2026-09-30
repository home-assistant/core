"""Test the Anthem A/V Receivers media player."""

from collections.abc import Callable
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityStateAttribute,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_update_states_zone1(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_anthemav: AsyncMock,
    update_callback: Callable[[str], None],
) -> None:
    """Test zone states are updated."""

    mock_zone = mock_anthemav.protocol.zones[1]

    mock_zone.power = True
    mock_zone.mute = True
    mock_zone.volume_as_percentage = 42
    mock_zone.input_name = "TEST INPUT"
    mock_zone.input_format = "2.0 PCM"
    mock_anthemav.protocol.input_list = ["TEST INPUT", "INPUT 2"]

    update_callback("command")
    await hass.async_block_till_done()

    states = hass.states.get("media_player.anthem_av")
    assert states
    assert states.state == STATE_ON
    assert states.attributes[MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL] == 42
    assert states.attributes[MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED] is True
    assert (
        states.attributes[MediaPlayerEntityStateAttribute.INPUT_SOURCE] == "TEST INPUT"
    )
    assert (
        states.attributes[MediaPlayerEntityStateAttribute.MEDIA_TITLE] == "TEST INPUT"
    )
    assert states.attributes[MediaPlayerEntityStateAttribute.APP_NAME] == "2.0 PCM"
    assert states.attributes[
        MediaPlayerEntityCapabilityAttribute.INPUT_SOURCE_LIST
    ] == ["TEST INPUT", "INPUT 2"]
