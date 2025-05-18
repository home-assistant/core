"""Tests for common SonosSpeaker behavior."""

from unittest.mock import patch

import pytest

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_PLAY,
)
from homeassistant.components.sonos import DOMAIN
from homeassistant.components.sonos.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SonosMockEvent

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    load_json_value_fixture,
)


async def test_fallback_to_polling(
    hass: HomeAssistant,
    config_entry,
    soco,
    fire_zgs_event,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that polling fallback works."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Do not wait on background tasks here because the
    # subscription callback will fire an unsub the polling check
    await hass.async_block_till_done()
    await fire_zgs_event()

    speaker = list(config_entry.runtime_data.sonos_data.discovered.values())[0]
    assert speaker.soco is soco
    assert speaker._subscriptions
    assert not speaker.subscriptions_failed

    caplog.clear()

    # Ensure subscriptions are cancelled and polling methods are called when subscriptions time out
    with (
        patch("homeassistant.components.sonos.media.SonosMedia.poll_media"),
        patch(
            "homeassistant.components.sonos.speaker.SonosSpeaker.subscription_address"
        ),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not speaker._subscriptions
    assert speaker.subscriptions_failed
    assert "Activity on Zone A from SonosSpeaker.update_volume" in caplog.text


async def test_subscription_creation_fails(
    hass: HomeAssistant, async_setup_sonos, config_entry: MockConfigEntry
) -> None:
    """Test that subscription creation failures are handled."""
    with patch(
        "homeassistant.components.sonos.speaker.SonosSpeaker._subscribe",
        side_effect=ConnectionError("Took too long"),
    ):
        await async_setup_sonos()
        await hass.async_block_till_done(wait_background_tasks=True)

    speaker = list(config_entry.runtime_data.sonos_data.discovered.values())[0]
    assert not speaker._subscriptions

    with patch.object(speaker, "_resub_cooldown_expires_at", None):
        speaker.speaker_activity("discovery")
        await hass.async_block_till_done()

    assert speaker._subscriptions


def _create_zgs_sonos_event(
    fixture_file: str, soco_1: MockSoCo, soco_2: MockSoCo, create_uui_ds: bool = True
) -> SonosMockEvent:
    """Create a Sonos Event for zone group state, with the option of creating the uui_ds_in_group."""
    zgs = load_fixture(fixture_file, DOMAIN)
    variables = {}
    variables["ZoneGroupState"] = zgs
    # Sonos does not always send this variable with zgs events
    if create_uui_ds:
        variables["zone_player_uui_ds_in_group"] = f"{soco_1.uid},{soco_2.uid}"
    event = SonosMockEvent(soco_1, soco_1.zoneGroupTopology, variables)
    if create_uui_ds:
        event.zone_player_uui_ds_in_group = f"{soco_1.uid},{soco_2.uid}"
    return event


def _create_avtransport_sonos_event(
    fixture_file: str, soco: MockSoCo
) -> SonosMockEvent:
    """Create a Sonos Event for an AVTransport update."""
    variables = load_json_value_fixture(fixture_file, DOMAIN)
    return SonosMockEvent(soco, soco.avTransport, variables)


async def _media_play(hass: HomeAssistant, entity: str) -> None:
    """Call media play service."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {
            "entity_id": entity,
        },
        blocking=True,
    )


async def test_zgs_event_group_speakers(
    hass: HomeAssistant, sonos_setup_two_speakers: list[MockSoCo]
) -> None:
    """Tests grouping and ungrouping two speakers."""
    # When Sonos speakers are grouped; one of the speakers is the coordinator and is in charge
    # of playback across both speakers. Hence, service calls to play or pause on media_players
    # that are part of the group are routed to the coordinator.
    soco_lr = sonos_setup_two_speakers[0]
    soco_br = sonos_setup_two_speakers[1]

    # Test 1 - Initial state - speakers are not grouped
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"] == ["media_player.living_room"]
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"] == ["media_player.bedroom"]
    # Each speaker is its own coordinator and calls should route to their SoCos
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 1
    await _media_play(hass, "media_player.bedroom")
    assert soco_br.play.call_count == 1

    soco_lr.play.reset_mock()
    soco_br.play.reset_mock()

    # Test 2 - Group the speakers, living room is the coordinator
    event = _create_zgs_sonos_event(
        "zgs_group.xml", soco_lr, soco_br, create_uui_ds=True
    )
    soco_lr.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_br.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"] == [
        "media_player.living_room",
        "media_player.bedroom",
    ]
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"] == [
        "media_player.living_room",
        "media_player.bedroom",
    ]
    # Play calls should route to the living room SoCo
    await _media_play(hass, "media_player.living_room")
    await _media_play(hass, "media_player.bedroom")
    assert soco_lr.play.call_count == 2
    assert soco_br.play.call_count == 0

    soco_lr.play.reset_mock()
    soco_br.play.reset_mock()

    # Test 3 - Ungroup the speakers
    event = _create_zgs_sonos_event(
        "zgs_two_single.xml", soco_lr, soco_br, create_uui_ds=False
    )
    soco_lr.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_br.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"] == ["media_player.living_room"]
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"] == ["media_player.bedroom"]
    # Calls should route to each speakers Soco
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 1
    await _media_play(hass, "media_player.bedroom")
    assert soco_br.play.call_count == 1


async def test_zgs_avtransport_group_speakers(
    hass: HomeAssistant, sonos_setup_two_speakers: list[MockSoCo]
) -> None:
    """Test processing avtransport and zgs events to change group membership."""
    soco_lr = sonos_setup_two_speakers[0]
    soco_br = sonos_setup_two_speakers[1]

    # Test 1 - Send a transport event changing the coordinator
    # for the living room speaker to the bedroom speaker.
    event = _create_avtransport_sonos_event("av_transport.json", soco_lr)
    soco_lr.avTransport.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Call should route to the new coodinator which is the bedroom
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 0
    assert soco_br.play.call_count == 1

    soco_lr.play.reset_mock()
    soco_br.play.reset_mock()

    # Test 2- Send a zgs event to return living room to its own coordinator
    event = _create_zgs_sonos_event(
        "zgs_two_single.xml", soco_lr, soco_br, create_uui_ds=False
    )
    soco_lr.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_br.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Call should route to the living room
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 1
    assert soco_br.play.call_count == 0
