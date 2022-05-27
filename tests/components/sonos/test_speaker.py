"""Tests for common SonosSpeaker behavior."""
from unittest.mock import patch

from homeassistant.components.sonos.const import DATA_SONOS, SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_fallback_to_polling(
    hass: HomeAssistant, async_autosetup_sonos, soco, caplog
):
    """Test that polling fallback works."""
    speaker = list(hass.data[DATA_SONOS].discovered.values())[0]
    assert speaker.soco is soco
    assert speaker._subscriptions

    caplog.clear()

    # Ensure subscriptions are cancelled and polling methods are called when subscriptions time out
    with patch("homeassistant.components.sonos.media.SonosMedia.poll_media"), patch(
        "homeassistant.components.sonos.speaker.SonosSpeaker.subscription_address"
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    assert not speaker._subscriptions
    assert speaker.subscriptions_failed
    assert "falling back to polling" in caplog.text
    assert "Activity on Zone A from SonosSpeaker.update_volume" in caplog.text
