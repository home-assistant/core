"""Test the jellyfin media source."""

from homeassistant.components import media_source
from homeassistant.components.jellyfin.const import DOMAIN, MAX_STREAMING_BITRATE
from homeassistant.components.media_source import const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_mock_jellyfin_config_entry
from .const import MOCK_AUTH_TOKEN, MOCK_TRACK_ID, MOCK_USER_ID, TEST_URL


async def test_async_resolve_track(hass: HomeAssistant) -> None:
    """Test resolving the URL for a valid audio item."""
    await setup_mock_jellyfin_config_entry(hass)

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    play_media = await media_source.async_resolve_media(
        hass,
        f"{const.URI_SCHEME}{DOMAIN}/{MOCK_TRACK_ID}",
    )

    assert (
        play_media.url
        == f"{TEST_URL}/Audio/{MOCK_TRACK_ID}/universal?UserId={MOCK_USER_ID}&DeviceId=Home+Assistant&api_key={MOCK_AUTH_TOKEN}&MaxStreamingBitrate={MAX_STREAMING_BITRATE}"
    )
