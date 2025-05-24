"""Tests for Sonos services."""

import asyncio
from contextlib import asynccontextmanager
import logging
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_JOIN,
    SERVICE_UNJOIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockSoCo, create_zgs_sonos_event


async def test_media_player_join(
    hass: HomeAssistant,
    sonos_setup_two_speakers: list[MockSoCo],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test joining two speakers together."""
    soco_living_room = sonos_setup_two_speakers[0]
    soco_bedroom = sonos_setup_two_speakers[1]

    # After dispatching the join to the speakers, the code waits for the
    # group to be updated before returning. To simulate this we will create
    # a ZGS event to simulate the speakers being grouped. This event is
    # triggered by the firing of the join_complete_event in the join mock.
    join_complete_event = asyncio.Event()

    def mock_join(*args, **kwargs):
        hass.loop.call_soon_threadsafe(join_complete_event.set)

    soco_bedroom.join = Mock(side_effect=mock_join)

    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {
                "entity_id": "media_player.living_room",
                "group_members": ["media_player.bedroom"],
            },
            blocking=False,
        )
        await join_complete_event.wait()
        # Fire the ZGS event to update the speaker grouping as the join method is waiting
        # for the speakers to be regrouped.
        event = create_zgs_sonos_event(
            "zgs_group.xml", soco_living_room, soco_bedroom, create_uui_ds=True
        )
        soco_living_room.zoneGroupTopology.subscribe.return_value._callback(event)
        soco_bedroom.zoneGroupTopology.subscribe.return_value._callback(event)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Code logs wanring messages if the join is not successful, so we check
    # that no warning messages were logged.
    assert len(caplog.records) == 0
    assert soco_bedroom.join.call_count == 1
    assert soco_bedroom.join.call_args[0][0] == soco_living_room
    assert soco_living_room.join.call_count == 0


async def test_media_player_join_bad_entity(
    hass: HomeAssistant,
    sonos_setup_two_speakers: list[MockSoCo],
) -> None:
    """Test error handling of joining with a bad entity."""

    # Ensure an error is raised if the entity is unknown
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {
                "entity_id": "media_player.living_room",
                "group_members": "media_player.bad_entity",
            },
            blocking=True,
        )
    assert "media_player.bad_entity" in str(excinfo.value)


@asynccontextmanager
async def instant_timeout(*args, **kwargs):
    """Mock a timeout error."""
    raise TimeoutError
    # This is never reached, but is needed to satisfy the asynccontextmanager
    yield  # pylint: disable=unreachable


async def test_media_player_join_timeout(
    hass: HomeAssistant,
    sonos_setup_two_speakers: list[MockSoCo],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test joining of two speakers with timeout error."""

    soco_living_room = sonos_setup_two_speakers[0]
    soco_bedroom = sonos_setup_two_speakers[1]

    with (
        patch(
            "homeassistant.components.sonos.speaker.asyncio.timeout", instant_timeout
        ),
        caplog.at_level(logging.WARNING),
    ):
        caplog.clear()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {
                "entity_id": "media_player.living_room",
                "group_members": ["media_player.bedroom"],
            },
            blocking=True,
        )
    assert soco_bedroom.join.call_count == 1
    assert soco_bedroom.join.call_args[0][0] == soco_living_room
    assert soco_living_room.join.call_count == 0
    assert "Timeout" in caplog.text
    assert "Living Room" in caplog.text
    assert "Bedroom" in caplog.text


async def test_media_player_unjoin(
    hass: HomeAssistant,
    sonos_setup_two_speakers: list[MockSoCo],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unjoing two speaker."""
    soco_living_room = sonos_setup_two_speakers[0]
    soco_bedroom = sonos_setup_two_speakers[1]

    # First group the speakers together
    event = create_zgs_sonos_event(
        "zgs_group.xml", soco_living_room, soco_bedroom, create_uui_ds=True
    )
    soco_living_room.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_bedroom.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Now that the speaker are joined, test unjoining
    unjoin_complete_event = asyncio.Event()

    def mock_unjoin(*args, **kwargs):
        hass.loop.call_soon_threadsafe(unjoin_complete_event.set)

    soco_bedroom.unjoin = Mock(side_effect=mock_unjoin)

    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_UNJOIN,
            {"entity_id": "media_player.bedroom"},
            blocking=False,
        )
        await unjoin_complete_event.wait()
        # Fire the ZGS event to ungroup the speakers as the unjoin method is waiting
        # for the speakers to be ungrouped.
        event = create_zgs_sonos_event(
            "zgs_two_single.xml", soco_living_room, soco_bedroom, create_uui_ds=False
        )
        soco_living_room.zoneGroupTopology.subscribe.return_value._callback(event)
        soco_bedroom.zoneGroupTopology.subscribe.return_value._callback(event)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(caplog.records) == 0
    assert soco_bedroom.unjoin.call_count == 1
    assert soco_living_room.unjoin.call_count == 0


async def test_media_player_unjoin_already_unjoined(
    hass: HomeAssistant,
    sonos_setup_two_speakers: list[MockSoCo],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unjoining when already unjoined."""
    soco_living_room = sonos_setup_two_speakers[0]
    soco_bedroom = sonos_setup_two_speakers[1]

    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_UNJOIN,
            {"entity_id": "media_player.bedroom"},
            blocking=True,
        )

    assert len(caplog.records) == 0
    # Should not have called unjoin, since the speakers are already unjoined.
    assert soco_bedroom.unjoin.call_count == 0
    assert soco_living_room.unjoin.call_count == 0
