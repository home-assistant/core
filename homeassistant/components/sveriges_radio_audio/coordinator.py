"""The coordinator that does something *shrug*"""

import mimetypes

from const import DOMAIN

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import PlayMedia

import xml.etree.ElementTree as ET
import requests

#async def async_get_media_source(hass: HomeAssistant) -> Coordinator:
#    """Set up Coordinator."""
#    # Radio browser supports only a single config entry
#    entry = hass.config_entries.async_entries(DOMAIN)[0]
#
#    return Coordinator(hass, entry)

class Coordinator():
    """Coordinator for Sveriges Radio."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Coordinator."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    async def async_resolve_media(self) -> PlayMedia:
        """Resolve selected Radio station to a streaming URL."""

        #Code below gets all the channels and puts all the IDs in a list
        url = 'http://api.sr.se/api/v2/channels'
        #https://http-live.sr.se/p1-mp3-128
        response = requests.get(url)

        if response.status_code != 200:
            raise Unresolvable("API is broken, help!")

        #channelIds = list()

        response_xml = ET.fromstring(response.text)

        #Use something like this to go through channels
#        for channel in response_xml.find('channels'):
#            channelIds.apppend(channel.attrib)

        #Code below selects a specific channel

        url_audio = response_xml.find('channels').find('channel').find('liveaudio').find('url').text

        print(url_audio)



        return PlayMedia(url_audio, mimetypes.guess_type(url_audio))

