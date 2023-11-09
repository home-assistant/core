"""The coordinator that does something *shrug*"""

import mimetypes

from const import DOMAIN

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)

import xml.etree.ElementTree as ET

async def async_get_media_source(hass: HomeAssistant) -> Coordinator:
    """Set up Coordinator."""
    # Radio browser supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return Coordinator(hass, entry)

class Coordinator():
    """Coordinator for Sveriges Radio."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Coordinator."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve selected Radio station to a streaming URL."""
        url = 'http://api.sr.se/api/v2/'
        #https://http-live.sr.se/p1-mp3-128
        response = ET.parse(requests.get(url)).getroot()
        channelIds = list()

        for channel in response.find('channels').iter():
            channelIds.apppend(channel.tag)

        return PlayMedia(url, mimetypes.guess_type(url))

