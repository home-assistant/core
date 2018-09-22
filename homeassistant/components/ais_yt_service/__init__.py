"""
Search the audio on YT
"""

import asyncio
import logging
import voluptuous as vol
import requests
import json
from homeassistant.helpers import config_validation as cv
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()
URL_BASE = 'https://www.googleapis.com/youtube/v3/search'
DEFAULT_ACTION = 'No video'
# DEPENDENCIES = ['http']

DOMAIN = 'ais_yt_service'
SERVICE_SEARCH = 'search'
SERVICE_SELECT_TRACK_NAME = 'select_track_name'
ATTR_QUERY = 'query'
ATTR_NAME = 'name'
SERVICE_SEARCH_SCHEMA = vol.Schema({
    vol.Required(ATTR_QUERY): cv.string,
})
G_YT_FOUND = []
G_YT_KEY = None
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})
    data = hass.data[DOMAIN] = YouTubeData(hass)
    yield from data.get_key_async()

    @asyncio.coroutine
    def search(service):
        """search service about audio"""
        _LOGGER.debug('search')
        yield from data.process_search_async(service)

    # @asyncio.coroutine
    def select_track_name(service):
        """select track name"""
        _LOGGER.debug('select_track_name')
        data.process_select_track_name(service)

    # register services
    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH, search, schema=SERVICE_SEARCH_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_TRACK_NAME, select_track_name)

    return True


class YouTubeData:
    """Class to hold YT data."""

    def __init__(self, hass):
        """Initialize the radio stations."""
        self.hass = hass

    @asyncio.coroutine
    def get_key_async(self):
        def load():
            global G_YT_KEY
            try:
                ws_resp = aisCloud.key("ytsearch")
                json_ws_resp = ws_resp.json()
                G_YT_KEY = json_ws_resp["key"]
            except:
                ais_global.G_OFFLINE_MODE = True

        yield from self.hass.async_add_job(load)

    @asyncio.coroutine
    def process_search_async(self, call):
        """Search in service."""
        global G_YT_FOUND
        global G_YT_KEY
        query = call.data[ATTR_QUERY]

        if G_YT_KEY is None:
            try:
                ws_resp = aisCloud.key("ytsearch")
                json_ws_resp = ws_resp.json()
                G_YT_KEY = json_ws_resp["key"]
            except:
                ais_global.G_OFFLINE_MODE = True
                yield from self.hass.services.async_call(
                    'ais_ai_service', 'say_it', {
                        "text": "Brak odpowiedzi, sprawdz połączenie z Intenetem"
                    })
                return

        params = dict(order='relevance',
                      part='snippet',
                      key=G_YT_KEY,
                      maxResults=50)
        params.update({'q': query})
        data = requests.get(URL_BASE, params=params).json()
        found = []
        titles = []
        for item in data['items']:
            if item['id']['kind'] == 'youtube#video':
                i = {}
                i["id"] = item['id']['videoId']
                i["title"] = item['snippet']['title']
                # i["description"] = item['snippet']['description']
                i["thumbnail"] = item['snippet']['thumbnails']['medium']['url']
                titles.append(item['snippet']['title'])
                found.append(i)
        G_YT_FOUND = found
        _LOGGER.debug('found' + str(found))
        # Update input_select values:
        yield from self.hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.ais_youtube_track_name",
                    "options": titles})

        text = "Znaleziono: %s, włączam pierwszy: %s" % (
            str(len(G_YT_FOUND)), G_YT_FOUND[0]["title"])
        _LOGGER.debug("text: " + text)
        yield from self.hass.services.async_call(
            'ais_ai_service', 'say_it', {
                "text": text
            })

    def process_select_track_name(self, call):
        _LOGGER.info("process_select_track_name")
        # """Search in last search return."""
        name = call.data[ATTR_NAME]
        for item in G_YT_FOUND:
            if item["title"] == name:
                item_id = item["id"]
                _audio_info = json.dumps(
                    {"IMAGE_URL": item["thumbnail"], "NAME": item["title"], "MEDIA_SOURCE": ais_global.G_AN_MUSIC}
                )

        player_name = self.hass.states.get(
            'input_select.ais_music_player').state
        player = ais_cloud.get_player_data(player_name)
        url = "https://www.youtube.com/watch?v="
        self.hass.services.call(
            'media_extractor',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_id": url + item_id,
                "media_content_type": "video/youtube"})

        # set stream image and title
        # if entity_id == 'media_player.wbudowany_glosnik':
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_type": "ais_info",
                "media_content_id": _audio_info
            })
