"""Tests for common SonosSpeaker behavior."""

from unittest.mock import patch

import pytest

from homeassistant.components import sonos
from homeassistant.components.sonos.const import DATA_SONOS, SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SoCoMockFactory, SonosMockEvent

from tests.common import async_fire_time_changed, load_fixture


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


async def test_zgs_event_group_speakers(
    hass: HomeAssistant, soco_factory: SoCoMockFactory
) -> None:
    """Test grouping two speaker together."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    zgs = load_fixture("sonos/zgs_group.xml")
    variables = {
        "ZoneGroupState": zgs,
        "zone_player_uui_ds_in_group": f"{soco_1.uid},{soco_2.uid}",
    }
    event = SonosMockEvent(soco_1, soco_1.zoneGroupTopology, variables)
    event.zone_player_uui_ds_in_group = f"{soco_1.uid},{soco_2.uid}"
    await _setup_hass(hass)
    soco_1.zoneGroupTopology.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("media_player.living_room")
    assert state.attributes["group_members"][0] == "media_player.living_room"
    assert state.attributes["group_members"][1] == "media_player.bedroom"
    state = hass.states.get("media_player.bedroom")
    assert state.attributes["group_members"][0] == "media_player.living_room"
    assert state.attributes["group_members"][1] == "media_player.bedroom"
