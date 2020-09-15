"""Test Local Media Source."""
import pytest

from homeassistant.components import media_source
from homeassistant.components.media_source import const
from homeassistant.components.media_source.models import PlayMedia
from homeassistant.components.netatmo import DATA_CAMERAS, DATA_EVENTS, DOMAIN
from homeassistant.setup import async_setup_component


async def test_async_browse_media(hass):
    """Test browse media."""
    assert await async_setup_component(hass, DOMAIN, {})

    # Prepare cached Netatmo event date
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_EVENTS] = {
        "12:34:56:78:90:ab": {
            1599152672: {
                "id": "12345",
                "type": "person",
                "time": 1599152672,
                "camera_id": "12:34:56:78:90:ab",
                "snapshot": {
                    "url": "https://netatmocameraimage",
                },
                "video_id": "98765",
                "video_status": "available",
                "message": "<b>Paulus</b> seen",
                "media_url": "http:///files/high/index.m3u8",
            },
            1599152673: {
                "id": "12346",
                "type": "person",
                "time": 1599152673,
                "camera_id": "12:34:56:78:90:ab",
                "snapshot": {
                    "url": "https://netatmocameraimage",
                },
                "message": "<b>Tobias</b> seen",
            },
            1599152674: {
                "id": "12347",
                "type": "outdoor",
                "time": 1599152674,
                "camera_id": "12:34:56:78:90:ac",
                "snapshot": {
                    "url": "https://netatmocameraimage",
                },
                "video_id": "98766",
                "video_status": "available",
                "event_list": [
                    {
                        "type": "vehicle",
                        "time": 1599152674,
                        "id": "12347-0",
                        "offset": 0,
                        "message": "Vehicle detected",
                        "snapshot": {
                            "url": "https://netatmocameraimage",
                        },
                    },
                    {
                        "type": "human",
                        "time": 1599152674,
                        "id": "12347-1",
                        "offset": 8,
                        "message": "Person detected",
                        "snapshot": {
                            "url": "https://netatmocameraimage",
                        },
                    },
                ],
                "media_url": "http:///files/high/index.m3u8",
            },
        }
    }

    hass.data[DOMAIN][DATA_CAMERAS] = {
        "12:34:56:78:90:ab": "MyCamera",
        "12:34:56:78:90:ac": "MyOutdoorCamera",
    }

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    # Test camera not exists
    with pytest.raises(media_source.BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/events/98:76:54:32:10:ff"
        )
    assert str(excinfo.value) == "Camera does not exist."

    # Test browse event
    with pytest.raises(media_source.BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/12345"
        )
    assert str(excinfo.value) == "Event does not exist."

    # Test invalid base
    with pytest.raises(media_source.BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/invalid/base"
        )
    assert str(excinfo.value) == "Unknown source directory."

    # Test successful listing
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/events/"
    )

    # Test successful events listing
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab"
    )

    # Test successful event listing
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/1599152672"
    )
    assert media

    # Test successful event resolve
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/1599152672"
    )
    assert media == PlayMedia(
        url="http:///files/high/index.m3u8", mime_type="application/x-mpegURL"
    )
