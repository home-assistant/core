"""Test Local Media Source."""
import ast

import pytest

from homeassistant.components import media_source
from homeassistant.components.media_source import const
from homeassistant.components.media_source.models import PlayMedia
from homeassistant.components.netatmo import DATA_CAMERAS, DATA_EVENTS, DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import load_fixture


async def test_async_browse_media(hass):
    """Test browse media."""
    assert await async_setup_component(hass, DOMAIN, {})

    # Prepare cached Netatmo event date
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_EVENTS] = ast.literal_eval(
        load_fixture("netatmo/events.txt")
    )

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

    # Test invalid base
    with pytest.raises(media_source.BrowseError) as excinfo:
        await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}/")
    assert str(excinfo.value) == "Invalid media source URI"

    # Test successful listing
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/events"
    )

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
        hass, f"{const.URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/1599152672", None
    )
    assert media == PlayMedia(
        url="http:///files/high/index.m3u8", mime_type="application/x-mpegURL"
    )
