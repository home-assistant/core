"""Tests for common SonosSpeaker behavior."""

from unittest.mock import patch

import pytest

from homeassistant.components import sonos
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_PLAY,
)
from homeassistant.components.sonos.const import DATA_SONOS, SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SoCoMockFactory, SonosMockEvent

from tests.common import async_fire_time_changed, load_fixture, load_json_value_fixture


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

    speaker = list(hass.data[DATA_SONOS].discovered.values())[0]
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
    hass: HomeAssistant, async_setup_sonos
) -> None:
    """Test that subscription creation failures are handled."""
    with patch(
        "homeassistant.components.sonos.speaker.SonosSpeaker._subscribe",
        side_effect=ConnectionError("Took too long"),
    ):
        await async_setup_sonos()
        await hass.async_block_till_done(wait_background_tasks=True)

    speaker = list(hass.data[DATA_SONOS].discovered.values())[0]
    assert not speaker._subscriptions

    with patch.object(speaker, "_resub_cooldown_expires_at", None):
        speaker.speaker_activity("discovery")
        await hass.async_block_till_done()

    assert speaker._subscriptions


async def _setup_hass(hass: HomeAssistant):
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {
            "sonos": {
                "media_player": {
                    "interface_addr": "127.0.0.1",
                    "hosts": ["10.10.10.1", "10.10.10.2"],
                }
            }
        },
    )
    await hass.async_block_till_done()


def _load_zgs(
    fixture_file: str, soco_1: MockSoCo, soco_2: MockSoCo, create_uui_ds: bool = True
) -> SonosMockEvent:
    zgs = load_fixture(f"sonos/{fixture_file}")
    variables = {}
    variables["ZoneGroupState"] = zgs
    if create_uui_ds:
        variables["zone_player_uui_ds_in_group"] = f"{soco_1.uid},{soco_2.uid}"
    event = SonosMockEvent(soco_1, soco_1.zoneGroupTopology, variables)
    if create_uui_ds:
        event.zone_player_uui_ds_in_group = f"{soco_1.uid},{soco_2.uid}"
    return event


def _load_avtransport(fixture_file: str, soco: MockSoCo) -> SonosMockEvent:
    variables = load_json_value_fixture(fixture_file, "sonos")
    return SonosMockEvent(soco, soco.avTransport, variables)


async def _media_play(hass: HomeAssistant, entity: str) -> None:
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {
            "entity_id": entity,
        },
        blocking=True,
    )


async def test_zgs_event_group_speakers(
    hass: HomeAssistant, soco_factory: SoCoMockFactory
) -> None:
    """Test grouping two speaker together."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    await _setup_hass(hass)

    # Initial state - speakers are not grouped
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"] == ["media_player.living_room"]
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"] == ["media_player.bedroom"]

    # Calls should route to each speakers Soco
    await _media_play(hass, "media_player.living_room")
    assert soco_1.play.call_count == 1
    await _media_play(hass, "media_player.bedroom")
    assert soco_2.play.call_count == 1

    soco_1.play.reset_mock()
    soco_2.play.reset_mock()

    # Group the speakers, living room is the coordinator and should be first
    event = _load_zgs("zgs_group.xml", soco_1, soco_2, create_uui_ds=True)
    soco_1.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_2.zoneGroupTopology.subscribe.return_value._callback(event)
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
    # Calls should all route to the group coordinator
    await _media_play(hass, "media_player.living_room")
    await _media_play(hass, "media_player.bedroom")
    assert soco_1.play.call_count == 2
    assert soco_2.play.call_count == 0

    soco_1.play.reset_mock()
    soco_2.play.reset_mock()

    # Ungroup the speakers
    event = _load_zgs("zgs_two_single.xml", soco_1, soco_2, create_uui_ds=False)
    soco_1.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_2.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"] == ["media_player.living_room"]
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"] == ["media_player.bedroom"]

    # Calls should route to each speakers Soco
    await _media_play(hass, "media_player.living_room")
    assert soco_1.play.call_count == 1
    await _media_play(hass, "media_player.bedroom")
    assert soco_2.play.call_count == 1

    soco_1.play.reset_mock()
    soco_2.play.reset_mock()


async def test_zgs_event_group_speakers_1(
    hass: HomeAssistant, soco_factory: SoCoMockFactory
) -> None:
    """Test grouping two speaker together."""
    soco_lr = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_br = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    await _setup_hass(hass)

    # Send a transport event that changes the coordinator for the Living Room speaker
    # to the bedroom speaker.
    event = _load_avtransport("av_transport.json", soco_lr)
    soco_lr.avTransport.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Calls should route to the new coodinator which is the bedroom
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 0
    assert soco_br.play.call_count == 1

    soco_lr.play.reset_mock()
    soco_br.play.reset_mock()

    # Send a zgs event that return the living room to it's own group
    event = _load_zgs("zgs_two_single.xml", soco_lr, soco_br, create_uui_ds=False)
    soco_lr.zoneGroupTopology.subscribe.return_value._callback(event)
    soco_br.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Calls should route to the living room
    await _media_play(hass, "media_player.living_room")
    assert soco_lr.play.call_count == 1
    assert soco_br.play.call_count == 0
