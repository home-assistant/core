"""
Search the audio on YT
"""
import asyncio
import logging
import requests
import json
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()
URL_BASE = 'https://www.googleapis.com/youtube/v3/search'
DEFAULT_ACTION = 'No video'

DOMAIN = 'ais_yt_service'
SERVICE_SEARCH = 'search'
ATTR_QUERY = 'query'
ATTR_NAME = 'name'

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
    def select_track_uri(service):
        """select track uri"""
        _LOGGER.debug('select_track_uri')
        data.process_select_track_uri(service)

    # register services
    hass.services.async_register(DOMAIN, SERVICE_SEARCH, search)
    hass.services.async_register(DOMAIN, 'select_track_uri', select_track_uri)

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
        global G_YT_KEY
        query = None
        if ATTR_QUERY in call.data:
            query = call.data[ATTR_QUERY]

        if query is None or len(query.strip()) == 0:
            # get tracks from favorites
            yield from self.hass.services.async_call(
                'ais_bookmarks', 'get_favorites', {"audio_source": ais_global.G_AN_MUSIC})
            return
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
        list_info = {}
        list_idx = 0
        for item in data['items']:
            if item['id']['kind'] == 'youtube#video':
                list_info[list_idx] = {}
                list_info[list_idx]["title"] = item['snippet']['title']
                list_info[list_idx]["name"] = item['snippet']['title']
                # item['snippet']['description']
                list_info[list_idx]["thumbnail"] = item['snippet']['thumbnails']['medium']['url']
                list_info[list_idx]["uri"] = item['id']['videoId']
                list_info[list_idx]["media_source"] = ais_global.G_AN_MUSIC
                list_info[list_idx]["audio_type"] = ais_global.G_AN_MUSIC
                list_info[list_idx]["icon"] = 'mdi:play'
                list_idx = list_idx + 1

        # update list
        self.hass.states.async_set("sensor.youtubelist", -1, list_info)

        if len(list_info) > 0:
            # from remote
            import homeassistant.components.ais_ai_service as ais_ai
            if ais_ai.CURR_ENTITIE == 'input_text.ais_music_query' and ais_ai.CURR_BUTTON_CODE == 4:
                ais_ai.set_curr_entity(self.hass, 'sensor.youtubelist')
                ais_ai.CURR_ENTITIE_ENTERED = True
                text = "Znaleziono: %s, wybierz pozycję którą mam włączyć" % (str(len(list_info)))
            else:
                text = "Znaleziono: %s, włączam pierwszy: %s" % (str(len(list_info)), list_info[0]["title"])
                yield from self.hass.services.async_call('ais_yt_service', 'select_track_uri', {"id": 0})
        else:
            text = "Brak wnyników na YouTube dla zapytania %s" % query
        # info to user
        yield from self.hass.services.async_call('ais_ai_service', 'say_it', {"text": text})

    def process_select_track_uri(self, call):
        _LOGGER.info("process_select_track_uri")
        # """play track by id on sensor list."""
        call_id = call.data["id"]
        state = self.hass.states.get('sensor.youtubelist')
        media_source = ais_global.G_AN_MUSIC
        if "media_source" in call.data:
            media_source = call.data["media_source"]
            if media_source == ais_global.G_AN_FAVORITE:
                state = self.hass.states.get('sensor.aisfavoriteslist')
            
        attr = state.attributes
        track = attr.get(int(call_id))
        url = "https://www.youtube.com/watch?v="
        # update list
        self.hass.states.async_set("sensor.youtubelist", call_id, attr)

        # try to get media url from AIS cloud
        media_url = None
        try:
            ws_resp = aisCloud.extract_media(url + track["uri"])
            json_ws_resp = ws_resp.json()
            _LOGGER.info(str(json_ws_resp))
            media_url = json_ws_resp["url"]
        except Exception as e:
            _LOGGER.error("extract_media error: " + str(e))

        all_ok = False
        if media_url is not None and len(media_url) > 0:
            # check 403
            import requests
            try:
                r = requests.head(media_url, allow_redirects=True, timeout=1)
                if r.status_code < 400:
                    all_ok = True
            except Exception as e:
                _LOGGER.warning("Request to youtube error " + str(e))

        if all_ok:
            # set stream url, image and title
            _audio_info = json.dumps(
                {"IMAGE_URL": track["thumbnail"], "NAME": track["title"], "lookup_url": track["uri"],
                 "MEDIA_SOURCE": media_source, "media_content_id": media_url})
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info
                })
        else:
            # use media_extractor to extract locally
            self.hass.services.call(
                'media_extractor',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_id": url + track["uri"],
                    "media_content_type": "video/youtube"})

            # set stream image and title
            _audio_info = json.dumps( {"IMAGE_URL": track["thumbnail"], "NAME": track["title"],
                                       "MEDIA_SOURCE": ais_global.G_AN_MUSIC, "lookup_url": track["uri"]})
            self.hass.services.call('media_player', 'play_media',
                                    {"entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                                     "media_content_type": "ais_info",
                                     "media_content_id": _audio_info})
