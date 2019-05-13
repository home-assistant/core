"""Component to manage the AIS Cloud."""
import asyncio
import logging
import requests
import json
import os
from homeassistant.ais_dom import ais_global
from homeassistant.const import EVENT_PLATFORM_DISCOVERED, EVENT_STATE_CHANGED
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import (CONF_NAME, CONF_IP_ADDRESS, CONF_MAC)
from homeassistant.util import slugify
DOMAIN = 'ais_cloud'
_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['feedparser==5.2.1', 'readability-lxml', 'bs4']
CLOUD_APP_URL = "https://powiedz.co/ords/f?p=100:1&x01=TOKEN:"
CLOUD_WS_TOKEN = None
CLOUD_WS_HEADER = {}
G_PLAYERS = []


def check_url(url_address):
    # check the 301 redirection
    try:
        r = requests.head(url_address, allow_redirects=True, timeout=1)
        return r.url
    except:
        return url_address


# Get player id by his name
def get_player_data(player_name):
    for player in G_PLAYERS:
        if player["friendly_name"] == player_name:
            return player


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the radio station list."""
    _LOGGER.info("Initialize the radio station list.")
    data = hass.data[DOMAIN] = AisColudData(hass)
    yield from data.get_types_async()

    # add "Console" panel to the menu list
    my_ip = ais_global.get_my_global_ip()
    yield from hass.components.frontend.async_register_built_in_panel(
            'iframe', "Konsola", "mdi:console",
            "console", {'url': 'http://' + my_ip + ':8888'})
    #
    hass.states.async_set("sensor.radiolist", -1, {})
    hass.states.async_set("sensor.podcastlist", -1, {})
    hass.states.async_set("sensor.podcastnamelist", -1, {})
    hass.states.async_set("sensor.youtubelist", -1, {})
    hass.states.async_set("sensor.spotifysearchlist", -1, {})
    hass.states.async_set("sensor.spotifylist", -1, {})
    hass.states.async_set("sensor.rssnewslist", -1, {})
    hass.states.async_set("sensor.rssnewstext", "", {"text": ""})
    hass.states.async_set("sensor.aisrsshelptext", "", {"text": ""})
    hass.states.async_set("sensor.aisknowledgeanswer", "", {"text": ""})



    def get_radio_types(call):
        _LOGGER.info("get_radio_types")
        data.get_radio_types(call)

    def get_radio_names(call):
        _LOGGER.info("get_radio_names")
        data.get_radio_names(call)

    def get_players(call):
        _LOGGER.info("get_players")
        data.get_players(call, hass)

    def play_audio(call):
        _LOGGER.info("play_audio")
        data.process_play_audio(call)

    def delete_audio(call):
        _LOGGER.info("delete_audio")
        data.process_delete_audio(call)

    def get_podcast_types(call):
        _LOGGER.info("get_podcast_types")
        data.get_podcast_types(call)

    def get_podcast_names(call):
        _LOGGER.info("get_podcast_names")
        data.get_podcast_names(call)

    def get_podcast_tracks(call):
        _LOGGER.info("get_podcast_tracks")
        data.get_podcast_tracks(call)

    def select_media_player(call):
        _LOGGER.info("select_media_player")
        data.select_media_player(call)

    def get_rss_news_category(call):
        _LOGGER.info("get_rss_news_category")
        data.get_rss_news_category(call)

    def get_rss_news_channels(call):
        _LOGGER.info("get_rss_news_channels")
        data.get_rss_news_channels(call)

    def get_rss_news_items(call):
        _LOGGER.info("get_rss_news_items")
        data.get_rss_news_items(call)

    def select_rss_news_item(call):
        _LOGGER.info("select_rss_news_item")
        data.select_rss_news_item(call)

    def select_rss_help_item(call):
        _LOGGER.info("select_rss_help_item")
        data.select_rss_help_item(call)

    def play_prev(call):
        _LOGGER.info("play_prev")
        data.play_prev(call)

    def play_next(call):
        _LOGGER.info("play_next")
        data.play_next(call)

    def change_audio_service(call):
        _LOGGER.info("change_audio_service")
        data.change_audio_service(call)

    # register services
    hass.services.async_register(DOMAIN, 'get_radio_types', get_radio_types)
    hass.services.async_register(DOMAIN, 'get_radio_names', get_radio_names)
    hass.services.async_register(DOMAIN, 'get_players', get_players)
    hass.services.async_register(DOMAIN, 'play_audio', play_audio)
    hass.services.async_register(DOMAIN, 'delete_audio', delete_audio)
    hass.services.async_register(DOMAIN, 'get_podcast_types', get_podcast_types)
    hass.services.async_register(DOMAIN, 'get_podcast_names', get_podcast_names)
    hass.services.async_register(DOMAIN, 'get_podcast_tracks', get_podcast_tracks)
    hass.services.async_register(DOMAIN, 'select_media_player', select_media_player)
    hass.services.async_register(DOMAIN, 'get_rss_news_category', get_rss_news_category)
    hass.services.async_register(DOMAIN, 'get_rss_news_channels', get_rss_news_channels)
    hass.services.async_register(DOMAIN, 'get_rss_news_items', get_rss_news_items)
    hass.services.async_register(DOMAIN, 'select_rss_news_item', select_rss_news_item)
    hass.services.async_register(DOMAIN, 'select_rss_help_item', select_rss_help_item)
    hass.services.async_register(DOMAIN, 'play_prev', play_prev)
    hass.services.async_register(DOMAIN, 'play_next', play_next)
    hass.services.async_register(DOMAIN, 'change_audio_service', change_audio_service)

    def device_discovered(service):
        """ Called when a device has been discovered. """
        _LOGGER.info("Discovered a new device type: " + str(service.as_dict()))
        try:
            d = service.as_dict().get('data')
            s = d.get('service')
            p = d.get('platform')
            if s == 'load_platform.sensor' and p == 'mqtt':
                i = d.get('discovered')
                uid = i.get('unique_id')
                if uid is not None:
                    # search entity_id for this unique_id
                    # add sensor to group
                    hass.async_add_job(
                        hass.services.async_call(
                            'group',
                            'set', {
                                "object_id": "all_ais_sensors",
                                "add_entities": ["sensor." + uid]
                            }
                        )
                    )
            elif s == 'load_platform.media_player':
                hass.async_add_job(
                    hass.services.async_call('ais_cloud', 'get_players')
                )

            _LOGGER.info("Discovered device prepare remote menu!")
            # prepare menu
            hass.async_add_job(
                hass.services.async_call(
                    'ais_ai_service',
                    'prepare_remote_menu'
                )
            )
        except Exception as e:
            _LOGGER.error("device_discovered: " + str(e))

    hass.bus.async_listen(EVENT_PLATFORM_DISCOVERED, device_discovered)

    def state_changed(state_event):
        """ Called on state change """
        entity_id = state_event.data.get('entity_id')
        if entity_id.startswith('media_player.'):
            _new = state_event.data['new_state'].attributes
            if state_event.data['old_state'] is None:
                _old = {'friendly_name': 'new ais dome device'}
            else:
                _old = state_event.data['old_state'].attributes
            # check if name was changed
            if _new['friendly_name'] != _old['friendly_name']:
                hass.async_add_job(
                    hass.services.async_call('ais_cloud', 'get_players')
                )
        elif entity_id == 'input_select.assistant_voice':
            voice = hass.states.get(entity_id).state
            if voice == 'Jola online':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda-network'
            elif voice == 'Jola lokalnie':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda-local'
            elif voice == 'Celina':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#female_1-local'
            elif voice == 'Anżela':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#female_2-local'
            elif voice == 'Asia':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#female_3-local'
            elif voice == 'Sebastian':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#male_1-local'
            elif voice == 'Bartek':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#male_2-local'
            elif voice == 'Andrzej':
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda#male_3-local'
            else:
                ais_global.GLOBAL_TTS_VOICE = 'pl-pl-x-oda-local'
        elif entity_id == 'input_number.assistant_rate':
            try:
                ais_global.GLOBAL_TTS_RATE = float(hass.states.get(entity_id).state)
            except Exception:
                ais_global.GLOBAL_TTS_RATE = 1
        elif entity_id == 'input_number.assistant_tone':
            try:
                ais_global.GLOBAL_TTS_PITCH = float(hass.states.get(entity_id).state)
            except Exception:
                ais_global.GLOBAL_TTS_PITCH = 1

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)
    return True


class AisCloudWS:
    def __init__(self):
        """Initialize the cloud WS connections."""
        self.url = "https://powiedz.co/ords/dom/dom/"

    def setCloudToken(self):
        # take the token from secrets
        global CLOUD_WS_TOKEN, CLOUD_WS_HEADER
        if CLOUD_WS_TOKEN is None:
            CLOUD_WS_TOKEN = ais_global.get_sercure_android_id_dom()
            CLOUD_WS_HEADER = {'Authorization': '{}'.format(CLOUD_WS_TOKEN)}

    def ask(self, question, org_answer):
        self.setCloudToken()
        payload = {'question': question, 'org_answer': org_answer}
        ws_resp = requests.get(self.url + 'ask', headers=CLOUD_WS_HEADER, params=payload, timeout=5)
        return ws_resp

    def audio_type(self, nature):
        self.setCloudToken()
        try:
            rest_url = self.url + "audio_type?nature=" + nature
            ws_resp = requests.get(rest_url, headers=CLOUD_WS_HEADER, timeout=5)
            return ws_resp
        except:
            _LOGGER.error("Can't connect to AIS Cloud!!! " + rest_url)
            ais_global.G_OFFLINE_MODE = True

    def audio_name(self, nature, a_type):
        self.setCloudToken()
        rest_url = self.url + "audio_name?nature=" + nature
        rest_url += "&type=" + a_type
        ws_resp = requests.get(rest_url, headers=CLOUD_WS_HEADER, timeout=5)
        return ws_resp

    def audio(self, item, a_type, text_input):
        self.setCloudToken()
        rest_url = self.url + "audio?item=" + item + "&type="
        rest_url += a_type + "&text_input=" + text_input
        ws_resp = requests.get(rest_url, headers=CLOUD_WS_HEADER, timeout=5)
        return ws_resp

    def key(self, service):
        self.setCloudToken()
        rest_url = self.url + "key?service=" + service
        ws_resp = requests.get(rest_url, headers=CLOUD_WS_HEADER, timeout=5)
        return ws_resp

    def extract_media(self, url):
        self.setCloudToken()
        rest_url = self.url + "extract_media?url=" + url
        ws_resp = requests.get(rest_url, headers=CLOUD_WS_HEADER, timeout=10)
        return ws_resp

    def delete_key(self, service):
        self.setCloudToken()
        rest_url = self.url + "key?service=" + service
        ws_resp = requests.delete(rest_url, headers=CLOUD_WS_HEADER, timeout=5)
        return ws_resp


class AisCacheData:
    def __init__(self, hass):
        """Initialize the files cache"""
        self.hass = hass
        self.persistence_radio = '/dom/radio_stations.json'
        self.persistence_podcast = '/dom/podcast.json'
        self.persistence_news = '/dom/news_chanels.json'

    def get_path(self, nature):
        path = str(os.path.dirname(__file__))
        if nature == ais_global.G_AN_RADIO:
            path = path + self.persistence_radio
        elif nature == ais_global.G_AN_PODCAST:
            path = path + self.persistence_podcast
        elif nature == ais_global.G_AN_NEWS:
            path = path + self.persistence_news
        return path

    def audio_type(self, nature):
        # get types from cache file
        path = self.get_path(nature)
        data = None
        if not os.path.isfile(path):
            return None
        else:
            with open(path) as file:
                data = json.loads(file.read())
        return data

    def store_audio_type(self, nature, json_data):
        path = self.get_path(nature)
        with open(path, 'w') as outfile:
            json.dump(json_data, outfile)

    def audio(self, item, type, text_input):
        return None


class AisColudData:
    """Class to hold radio stations data."""

    def __init__(self, hass):
        self.hass = hass
        self.audio_name = None
        self.cloud = AisCloudWS()
        self.cache = AisCacheData(hass)
        self.news_channels = []

    @asyncio.coroutine
    def get_types_async(self):
        def load():
            # check if we have data stored in local files
            # otherwise we should work in online mode and get data from cloud
            # ----------------
            # ----- RADIO ----
            # ----------------
            ws_resp = self.cloud.audio_type(ais_global.G_AN_RADIO)
            if ws_resp is None:
                json_ws_resp = self.cache.audio_type(ais_global.G_AN_RADIO)
            else:
                json_ws_resp = ws_resp.json()
                self.cache.store_audio_type(ais_global.G_AN_RADIO, json_ws_resp)

            types = [ais_global.G_EMPTY_OPTION]
            for item in json_ws_resp["data"]:
                types.append(item)
            # populate list with all stations from selected type
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.radio_type",
                    "options": types})
            # ----------------
            # --- PODCASTS ---
            # ----------------
            ws_resp = self.cloud.audio_type(ais_global.G_AN_PODCAST)
            if ws_resp is None:
                json_ws_resp = self.cache.audio_type(ais_global.G_AN_PODCAST)
            else:
                json_ws_resp = ws_resp.json()
                self.cache.store_audio_type(ais_global.G_AN_PODCAST, json_ws_resp)
            types = [ais_global.G_EMPTY_OPTION]
            for item in json_ws_resp["data"]:
                types.append(item)
            # populate list with all podcast from selected type
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.podcast_type",
                    "options": types})
            # ----------------
            # ----- NEWS -----
            # ----------------
            ws_resp = self.cloud.audio_type(ais_global.G_AN_NEWS)
            if ws_resp is None:
                json_ws_resp = self.cache.audio_type(ais_global.G_AN_NEWS)
            else:
                json_ws_resp = ws_resp.json()
                self.cache.store_audio_type(ais_global.G_AN_NEWS, json_ws_resp)
            types = [ais_global.G_EMPTY_OPTION]
            for item in json_ws_resp["data"]:
                types.append(item)
            # populate list with all news types from selected type
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.rss_news_category",
                    "options": types})
        yield from self.hass.async_add_job(load)

    def get_radio_types(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_RADIO)
        json_ws_resp = ws_resp.json()
        types = [ais_global.G_FAVORITE_OPTION]
        for item in json_ws_resp["data"]:
            types.append(item)
        # populate list with all stations from selected type
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.radio_type",
                "options": types})

    def get_radio_names(self, call):
        """Load stations of the for the selected type."""
        if "radio_type" not in call.data:
            _LOGGER.error("No radio_type")
            return []

        if call.data["radio_type"] == ais_global.G_FAVORITE_OPTION:
            # get radio stations from favorites
            self.hass.services.call('ais_bookmarks', 'get_favorites', {"audio_source": ais_global.G_AN_RADIO})
            return

        ws_resp = self.cloud.audio_name(ais_global.G_AN_RADIO, call.data["radio_type"])
        json_ws_resp = ws_resp.json()
        list_info = {}
        list_idx = 0
        for item in json_ws_resp["data"]:
            list_info[list_idx] = {}
            list_info[list_idx]["title"] = item["NAME"]
            list_info[list_idx]["name"] = item["NAME"]
            list_info[list_idx]["thumbnail"] = item["IMAGE_URL"]
            list_info[list_idx]["uri"] = item["STREAM_URL"]
            list_info[list_idx]["mediasource"] = ais_global.G_AN_RADIO
            list_info[list_idx]["audio_type"] = ais_global.G_AN_RADIO
            list_info[list_idx]["icon"] = 'mdi:play'
            list_idx = list_idx + 1

        # create lists
        self.hass.states.async_set("sensor.radiolist", -1, list_info)

        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'input_select.radio_type' and ais_ai.CURR_BUTTON_CODE == 23:
            ais_ai.set_curr_entity(self.hass, 'sensor.radiolist')
            self.hass.services.call('ais_ai_service', 'say_it', {"text": "Wybierz stację"})

    def get_podcast_types(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_PODCAST)
        json_ws_resp = ws_resp.json()
        types = [ais_global.G_FAVORITE_OPTION]
        for item in json_ws_resp["data"]:
            types.append(item)
        # populate list with all podcast types
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.podcast_type",
                "options": types})

    def get_podcast_names(self, call):
        """Load podcasts names for the selected type."""
        if "podcast_type" not in call.data:
            _LOGGER.error("No podcast_type")
            return []
        if call.data["podcast_type"] == ais_global.G_FAVORITE_OPTION:
            # get podcasts from favorites
            self.hass.services.call('ais_bookmarks', 'get_favorites', {"audio_source": ais_global.G_AN_PODCAST})
            return
        ws_resp = self.cloud.audio_name(ais_global.G_AN_PODCAST, call.data["podcast_type"])
        json_ws_resp = ws_resp.json()
        list_info = {}
        list_idx = 0
        for item in json_ws_resp["data"]:
            list_info[list_idx] = {}
            list_info[list_idx]["title"] = item["NAME"]
            list_info[list_idx]["name"] = item["NAME"]
            list_info[list_idx]["thumbnail"] = item["IMAGE_URL"]
            list_info[list_idx]["uri"] = item["LOOKUP_URL"]
            list_info[list_idx]["mediasource"] = ais_global.G_AN_PODCAST
            list_info[list_idx]["audio_type"] = ais_global.G_AN_PODCAST
            list_info[list_idx]["icon"] = 'mdi:podcast'
            list_idx = list_idx + 1

        # create lists
        self.hass.states.async_set("sensor.podcastnamelist", -1, list_info)

        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'input_select.podcast_type' and ais_ai.CURR_BUTTON_CODE == 23:
            ais_ai.set_curr_entity(self.hass, 'sensor.podcastnamelist')
            self.hass.services.call('ais_ai_service', 'say_it', {"text": "Wybierz audycję"})

    def get_podcast_tracks(self, call):
        import feedparser
        import io
        import homeassistant.components.ais_ai_service as ais_ai
        selected_by_remote = False
        if ais_ai.CURR_ENTITIE == 'sensor.podcastnamelist' and ais_ai.CURR_BUTTON_CODE == 23:
            selected_by_remote = True
        if "podcast_name" not in call.data:
            _LOGGER.error("No podcast_name")
            return
        if call.data["podcast_name"] == ais_global.G_FAVORITE_OPTION:
            # get podcasts from favorites
            self.hass.services.call('ais_bookmarks', 'get_favorites', {"audio_source": ais_global.G_AN_PODCAST})
            return

        podcast_name = call.data["podcast_name"]
        self.hass.services.call('ais_ai_service', 'say_it', {"text": "Pobieram odcinki audycji " + podcast_name})
        if "lookup_url" in call.data:
            _lookup_url = call.data["lookup_url"]
            _image_url = call.data["image_url"]
            selected_by_voice_command = True
        else:
            # the podcast was selected from select list in app
            _lookup_url = None
            _image_url = None
            selected_by_voice_command = False
            for podcast in self.podcast_names:
                if podcast["NAME"] == podcast_name:
                    _lookup_url = podcast["LOOKUP_URL"]
                    _image_url = podcast["IMAGE_URL"]
                    break
        if "media_source" in call.data:
            media_source = call.data["media_source"]
        else:
            media_source = ais_global.G_AN_PODCAST
        if _lookup_url is not None:
            try:
                try:
                    resp = requests.get(check_url(_lookup_url), timeout=3.0)
                except requests.ReadTimeout:
                    _LOGGER.warning("Timeout when reading RSS %s", _lookup_url)
                    self.hass.services.call(
                        'ais_ai_service', 'say_it',
                        {"text": "Nie można pobrać odcinków. Brak odpowiedzi z " + podcast_name})
                    return
                # Put it to memory stream object universal feedparser
                content = io.BytesIO(resp.content)
                # Parse content
                d = feedparser.parse(content)
                list_info = {}
                list_idx = 0
                for e in d.entries:
                    # list
                    list_info[list_idx] = {}
                    try:
                        list_info[list_idx]["thumbnail"] = d.feed.image.href
                    except Exception:
                        list_info[list_idx]["thumbnail"] = _image_url
                    list_info[list_idx]["title"] = e.title
                    list_info[list_idx]["name"] = e.title
                    list_info[list_idx]["uri"] = e.enclosures[0]
                    list_info[list_idx]["media_source"] = ais_global.G_AN_PODCAST
                    list_info[list_idx]["audio_type"] = ais_global.G_AN_PODCAST
                    list_info[list_idx]["icon"] = 'mdi:play'
                    list_info[list_idx]["lookup_url"] = _lookup_url
                    list_info[list_idx]["lookup_name"] = podcast_name
                    list_idx = list_idx + 1

                # update list
                self.hass.states.async_set("sensor.podcastlist", -1, list_info)
                if selected_by_voice_command:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": "Pobrano " + str(len(d.entries))
                            + " odcinków"
                            + ", audycji " + podcast_name
                            + ", włączam najnowszy odcinek: " + list_info[0]["title"]
                        })
                    # play it
                    self.hass.services.call('ais_cloud', 'play_audio',
                                            {"id": 0, "media_source": ais_global.G_AN_PODCAST,
                                             "lookup_url": _lookup_url, "lookup_name": podcast_name})
                else:
                    # check if the change was done form remote
                    if selected_by_remote:
                        if len(d.entries) > 0:
                            ais_ai.set_curr_entity(self.hass, 'sensor.podcastlist')
                            self.hass.services.call('ais_ai_service', 'say_it', {
                                "text": "Pobrano " + str(len(d.entries)) + " odcinków, wybierz odcinek"})
                        else:
                            self.hass.services.call('ais_ai_service', 'say_it', {"text": "Brak odcinków"})
                    else:
                        self.hass.services.call('ais_ai_service', 'say_it', {
                                "text": "Pobrano " + str(len(d.entries))
                                + " odcinków"
                                + ", audycji " + podcast_name
                            })
            except Exception as e:
                _LOGGER.error("Error: " + str(e))
                self.hass.services.call(
                    'ais_ai_service', 'say_it', {"text": "Nie można pobrać odcinków. " + podcast_name})

    def process_delete_audio(self, call):
        _LOGGER.info("process_delete_audio")
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_FAVORITE:
            self.hass.services.call('ais_bookmarks', 'delete_favorite', {"id": call.data['id']})
        elif media_source == ais_global.G_AN_BOOKMARK:
            self.hass.services.call('ais_bookmarks', 'delete_bookmark', {"id": call.data['id']})

    def process_play_audio(self, call):
        _LOGGER.info("process_play_audio")
        media_source = call.data["media_source"]
        if 'id' in call.data:
            if media_source == ais_global.G_AN_SPOTIFY_SEARCH:
                self.hass.services.call('ais_spotify_service', 'select_search_uri', {"id": call.data['id']})
                return
            elif media_source == ais_global.G_AN_SPOTIFY:
                self.hass.services.call('ais_spotify_service', 'select_track_uri', {"id": call.data['id']})
                return
            elif media_source == ais_global.G_AN_MUSIC:
                self.hass.services.call('ais_yt_service', 'select_track_uri', {"id": call.data['id']})
                return
            #
            if media_source == ais_global.G_AN_RADIO:
                track_list = 'sensor.radiolist'
            elif media_source == ais_global.G_AN_PODCAST:
                track_list = 'sensor.podcastlist'
            elif media_source == ais_global.G_AN_NEWS:
                track_list = 'sensor.rssnewslist'
            elif media_source == ais_global.G_AN_BOOKMARK:
                track_list = 'sensor.aisbookmarkslist'
            elif media_source == ais_global.G_AN_FAVORITE:
                track_list = 'sensor.aisfavoriteslist'
            elif media_source == ais_global.G_AN_PODCAST_NAME:
                track_list = 'sensor.podcastnamelist'

            state = self.hass.states.get(track_list)
            attr = state.attributes
            track = attr.get(int(call.data['id']))

            # update list
            if media_source == ais_global.G_AN_FAVORITE:
                self.hass.states.async_set(track_list, int(call.data['id']), attr)

            if media_source == ais_global.G_AN_NEWS:
                self.hass.services.call('ais_cloud', 'select_rss_news_item', {"id": call.data['id']})

            elif media_source in (ais_global.G_AN_PODCAST_NAME, ais_global.G_AN_FAVORITE)\
                    and track["audio_type"] == ais_global.G_AN_PODCAST:
                # selected from favorite - get the podcast tracks
                self.hass.services.call('ais_cloud', 'get_podcast_tracks', {"lookup_url": track["uri"],
                                                                            "podcast_name": track["name"],
                                                                            "image_url": track["thumbnail"],
                                                                            "media_source": ais_global.G_AN_FAVORITE})
            elif media_source == ais_global.G_AN_FAVORITE and track["audio_type"] == ais_global.G_AN_MUSIC:
                # selected from favorite - get the yt url
                self.hass.services.call('ais_yt_service', 'select_track_uri',
                                        {"id": call.data['id'], "media_source": ais_global.G_AN_FAVORITE})

            elif media_source in (ais_global.G_AN_RADIO, ais_global.G_AN_PODCAST):
                lookup_url = ""
                lookup_name = ""
                if media_source == ais_global.G_AN_PODCAST:
                    lookup_url = track["lookup_url"]
                    lookup_name = track["lookup_name"]
                try:
                    track_uri = track["uri"]["href"]
                except Exception:
                    track_uri = track["uri"]
                # update list
                self.hass.states.async_set(track_list, call.data['id'], attr)
                # set stream uri, image and title
                _audio_info = json.dumps(
                    {"IMAGE_URL": track["thumbnail"], "NAME": track["title"], "MEDIA_SOURCE": media_source,
                     "media_content_id": track_uri, "lookup_url": lookup_url, "lookup_name": lookup_name,
                     "audio_type": track["audio_type"]})
                self.hass.services.call('media_player', 'play_media',
                                        {"entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                                         "media_content_type": "ais_content_info",
                                         "media_content_id": _audio_info})
                return
            elif media_source == ais_global.G_AN_BOOKMARK:
                self.hass.states.async_set(track_list, call.data['id'], attr)
                self.hass.services.call('ais_bookmarks', 'play_bookmark', {"id": call.data['id']})
                return
            elif media_source == ais_global.G_AN_FAVORITE:
                self.hass.states.async_set(track_list, call.data['id'], attr)
                self.hass.services.call('ais_bookmarks', 'play_favorite', {"id": call.data['id']})
                return

        else:
            # play by voice
            if media_source == ais_global.G_AN_RADIO:
                # set stream uri, image and title
                _audio_info = {"IMAGE_URL": call.data["image_url"], "NAME": call.data["name"],
                               "MEDIA_SOURCE": ais_global.G_AN_RADIO,
                               "media_content_id": check_url(call.data["stream_url"])}
                _audio_info = json.dumps(_audio_info)
                self.hass.services.call('media_player', 'play_media',
                                        {"entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                                         "media_content_type": "ais_content_info",
                                         "media_content_id": _audio_info})

                # switch UI to Radio
                self.hass.services.call('ais_ai_service', 'switch_ui', {"mode": 'Radio'})

                #  get list
                self.hass.services.call('input_select', 'select_option',
                                        {"entity_id": "input_select.radio_type", "option": call.data["type"]})

            elif media_source == ais_global.G_AN_PODCAST:
                self.hass.services.call('input_select', 'select_option', {
                    "entity_id": "input_select.podcast_type",
                    "option": call.data["type"]})

                self.hass.services.call('ais_cloud', 'get_podcast_tracks', {"lookup_url": call.data["lookup_url"],
                                                                            "podcast_name": call.data["name"],
                                                                            "image_url": call.data["image_url"]})
                # switch UI to Podcast
                self.hass.services.call('ais_ai_service', 'switch_ui', {"mode": 'Podcast'})

    def play_prev(self, call):
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_RADIO:
            track_list = 'sensor.radiolist'
        elif media_source == ais_global.G_AN_PODCAST:
            track_list = 'sensor.podcastlist'
        elif media_source == ais_global.G_AN_MUSIC:
            track_list = 'sensor.youtubelist'
        elif media_source == ais_global.G_AN_SPOTIFY_SEARCH:
            track_list = 'sensor.spotifysearchlist'
        elif media_source == ais_global.G_AN_SPOTIFY:
            track_list = 'sensor.spotifylist'
        elif media_source == ais_global.G_AN_BOOKMARK:
            track_list = 'sensor.aisbookmarkslist'
        elif media_source == ais_global.G_AN_FAVORITE:
            track_list = 'sensor.aisfavoriteslist'
        else:
            return

        # get prev from list
        state = self.hass.states.get(track_list)
        curr_id = int(state.state)
        attr = state.attributes
        prev_id = curr_id - 1
        if prev_id < 0:
            prev_id = len(attr) - 1
        track = attr.get(int(prev_id))
        # say only if from remote
        import homeassistant.components.ais_ai_service as ais_ai
        #  binary_sensor.selected_entity / binary_sensor.ais_remote_button
        if ais_ai.CURR_ENTITIE == 'media_player.wbudowany_glosnik' and ais_ai.CURR_BUTTON_CODE in(21, 22):
            self.hass.services.call('ais_ai_service', 'say_it', {"text": track["title"]})
        # play
        self.hass.services.call('ais_cloud', 'play_audio', {"media_source": media_source, "id": prev_id})

    def play_next(self, call):
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_RADIO:
            track_list = 'sensor.radiolist'
        elif media_source == ais_global.G_AN_PODCAST:
            track_list = 'sensor.podcastlist'
        elif media_source == ais_global.G_AN_MUSIC:
            track_list = 'sensor.youtubelist'
        elif media_source == ais_global.G_AN_SPOTIFY_SEARCH:
            track_list = 'sensor.spotifysearchlist'
        elif media_source == ais_global.G_AN_SPOTIFY:
            track_list = 'sensor.spotifylist'
        elif media_source == ais_global.G_AN_BOOKMARK:
            track_list = 'sensor.aisbookmarkslist'
        elif media_source == ais_global.G_AN_FAVORITE:
            track_list = 'sensor.aisfavoriteslist'
        else:
            return
        # get next from list
        state = self.hass.states.get(track_list)
        curr_id = state.state
        attr = state.attributes
        next_id = int(curr_id) + 1
        if next_id == len(attr):
            next_id = 0
        track = attr.get(int(next_id))
        # say only if from remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'media_player.wbudowany_glosnik' and ais_ai.CURR_BUTTON_CODE in(21, 22):
            self.hass.services.call('ais_ai_service', 'say_it', {"text": track["title"]})
        # play
        self.hass.services.call('ais_cloud', 'play_audio', {"media_source": media_source, "id": next_id})

    def change_audio_service(self, call):
        # we have only 2 now we can toggle
        self.hass.services.call('input_select', 'select_next', {"entity_id": "input_select.ais_music_service"})

    def select_media_player(self, call):
        if "media_player_type" not in call.data:
            _LOGGER.error("No media_player_type")
            return
        player_name = None
        _url = None
        _audio_info = {}
        # TODO
        if player_name is not None:
            player = get_player_data(player_name)
        if _url is not None:
            # play media on selected device
            _audio_info["media_content_id"] = check_url(_url)
            # set stream image and title
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": json.dumps(_audio_info)
                })

    def get_players(self, call, hass):
        global G_PLAYERS
        G_PLAYERS = []
        players_lv = []
        if "device_name" in call.data:
            # check if this device already exists
            name = slugify(call.data.get('device_name'))
            m_player = hass.states.get('media_player.' + name)
            if m_player is None:
                _LOGGER.info("Adding new ais dom player " + name)
                hass.async_run_job(
                    async_load_platform(
                        hass, 'media_player', 'ais_exo_player',
                        {
                            CONF_NAME: call.data.get('device_name'),
                            CONF_IP_ADDRESS: call.data.get(CONF_IP_ADDRESS),
                            CONF_MAC: call.data.get(CONF_MAC)
                        },
                        hass.config))

        # take the info about normal players
        entities = hass.states.async_all()
        for entity in entities:
            if entity.entity_id.startswith('media_player.'):
                player = {}
                friendly_name = entity.attributes.get('friendly_name')
                device_ip = entity.attributes.get('device_ip')
                player['friendly_name'] = friendly_name
                player['entity_id'] = entity.entity_id
                player['device_ip'] = device_ip
                G_PLAYERS.append(player)
                players_lv.append(friendly_name)
                # add player to group if it's not added
                hass.async_add_job(
                    hass.services.async_call(
                        'group',
                        'set', {
                            "object_id": "audio_player",
                            "add_entities": [entity.entity_id]}))
        # TODO remove Podłączony głośnik from the list
        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.tts_player",
                    "options": players_lv}))
        # rebuild the groups
        import homeassistant.components.ais_ai_service as ais_ai
        ais_ai.get_groups(hass)

    def get_rss_news_category(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_NEWS)
        json_ws_resp = ws_resp.json()
        self.cache.store_audio_type(ais_global.G_AN_NEWS, json_ws_resp)
        types = [ais_global.G_EMPTY_OPTION]
        for item in json_ws_resp["data"]:
            types.append(item)
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.rss_news_category",
                "options": types})

    def get_rss_news_channels(self, call):
        """Load news channels of the for the selected category."""
        if "rss_news_category" not in call.data:
            _LOGGER.error("No rss_news_category")
            return []
        if call.data["rss_news_category"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.rss_news_channel",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return
        ws_resp = self.cloud.audio_name(
            ais_global.G_AN_NEWS, call.data["rss_news_category"])
        json_ws_resp = ws_resp.json()
        names = [ais_global.G_EMPTY_OPTION]
        self.news_channels = []
        for item in json_ws_resp["data"]:
            names.append(item["NAME"])
            self.news_channels.append(item)
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.rss_news_channel",
                "options": names})
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'input_select.rss_news_category' and ais_ai.CURR_BUTTON_CODE == 23:
            ais_ai.set_curr_entity(self.hass, 'input_select.rss_news_channel')
            self.hass.services.call('ais_ai_service', 'say_it', {"text": "Wybierz kanał wiadomości"})

    def get_rss_news_items(self, call):
        import feedparser
        import io
        if "rss_news_channel" not in call.data:
            _LOGGER.error("No rss_news_channel")
            return
        if call.data["rss_news_channel"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call('input_select', 'set_options', {"entity_id": "input_select.rss_news_item",
                                                                    "options": [ais_global.G_EMPTY_OPTION]})
            self.hass.states.async_set("sensor.rssnewslist", -1, {})
            return
        rss_news_channel = call.data["rss_news_channel"]
        if "lookup_url" in call.data:
            _lookup_url = call.data["lookup_url"]
            _image_url = call.data["image_url"]
            selected_by_voice_command = True
        else:
            # the news was selected from select list in app
            _lookup_url = None
            _image_url = None
            selected_by_voice_command = False
            for channel in self.news_channels:
                if channel["NAME"] == rss_news_channel:
                    _lookup_url = channel["LOOKUP_URL"]
                    _image_url = channel["IMAGE_URL"]
                    break

        if _lookup_url is not None:
            # download the episodes
            self.hass.services.call('ais_ai_service', 'say_it', {"text": "pobieram"})
            try:
                try:
                    resp = requests.get(check_url(_lookup_url), timeout=3.0)
                except requests.ReadTimeout:
                    _LOGGER.warning("Timeout when reading RSS %s", _lookup_url)
                    self.hass.services.call(
                        'ais_ai_service', 'say_it',
                        {"text": "Nie można wiadomości . Brak odpowiedzi z " + rss_news_channel})
                    return
                content = io.BytesIO(resp.content)
                # Parse content
                d = feedparser.parse(content)
                list_info = {}
                list_idx = 0
                for e in d.entries:
                    list_info[list_idx] = {}
                    list_info[list_idx]["title"] = e.title
                    list_info[list_idx]["name"] = e.title
                    list_info[list_idx]["description"] = e.description
                    list_info[list_idx]["thumbnail"] = _image_url
                    list_info[list_idx]["uri"] = e.link
                    list_info[list_idx]["mediasource"] = ais_global.G_AN_NEWS
                    list_info[list_idx]["type"] = ''
                    list_info[list_idx]["icon"] = 'mdi:voice'
                    list_idx = list_idx + 1

                # update list
                self.hass.states.async_set("sensor.rssnewslist", -1, list_info)

                if len(d.entries) == 0:
                    self.hass.services.call('ais_ai_service', 'say_it', {"text": "brak artykułów, wybierz inny kanał"})
                    return

                if selected_by_voice_command:
                    self.hass.services.call('ais_ai_service', 'say_it',
                                            {"text": "mamy " + str(len(d.entries)) + " wiadomości z "
                                                     + rss_news_channel
                                                     + ", czytam najnowszy artykuł: " + list_info[0]["title"]})

                    self.hass.states.async_set("sensor.rssnewslist", 0, list_info)
                    # call to read
                    # select_rss_news_item
                    # TODO
                else:
                    self.hass.services.call('ais_ai_service', 'say_it', {
                        "text": "mamy " + str(len(d.entries)) + " wiadomości, wybierz artykuł"})
                    # check if the change was done form remote
                    import homeassistant.components.ais_ai_service as ais_ai
                    if ais_ai.CURR_ENTITIE == 'input_select.rss_news_channel' and ais_ai.CURR_BUTTON_CODE == 23:
                        ais_ai.set_curr_entity(self.hass, 'sensor.rssnewslist')

            except Exception as e:
                _LOGGER.error("Error: " + str(e))
                self.hass.services.call('ais_ai_service', 'say_it',
                                        {"text": "Nie można pobrać wiadomości z: " + rss_news_channel})

    def select_rss_news_item(self, call):
        """Get text for the selected item."""
        if "id" not in call.data:
            _LOGGER.error("No rss news id")
            return
        news_text = ""
        # find the url and read the text
        rss_news_item_id = int(call.data["id"])
        state = self.hass.states.get('sensor.rssnewslist')
        attr = state.attributes
        track = attr.get(rss_news_item_id)
        # update list
        self.hass.states.async_set('sensor.rssnewslist', rss_news_item_id, attr)

        if track['description'] is not None:
            news_text = track['description']

        if track['uri'] is not None:
            try:
                import requests
                from readability import Document
                response = requests.get(check_url(track['uri']), timeout=5)
                response.encoding = 'utf-8'
                doc = Document(response.text)
                doc_s = doc.summary()
                if len(doc_s) > 0:
                    news_text = doc_s
            except Exception as e:
                _LOGGER.error("Can not get article " + str(e))

        from bs4 import BeautifulSoup
        clear_text = BeautifulSoup(news_text, "lxml").text
        self.hass.services.call('ais_ai_service', 'say_it', {"text": clear_text})
        news_text = news_text.replace("<html>", "")
        news_text = news_text.replace("</html>", "")
        news_text = news_text.replace("<body>", "")
        news_text = news_text.replace("</body>", "")
        self.hass.states.async_set('sensor.rssnewstext', news_text[:200], {'text': "" + news_text})

    def select_rss_help_item(self, call):
        """Get text for the selected item."""
        rss_help_text = ''
        if "rss_help_topic" not in call.data:
            _LOGGER.error("No rss_help_topic")
            return
        if call.data["rss_help_topic"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.states.async_set('sensor.aisrsshelptext', "-", {'text': "", 'friendly_name': "Tekst strony"})
            return
        # we need to build the url and get the text to read
        rss_help_topic = call.data["rss_help_topic"]
        _url = check_url(
            "https://raw.githubusercontent.com/wiki/sviete/AIS-WWW/" + rss_help_topic.replace(" ", "-") + ".md")
        import requests
        from readability import Document

        response = requests.get(_url, timeout=5)
        doc = Document(response.text)
        rss_help_text += doc.summary()

        from markdown import markdown
        rss_help_text = markdown(rss_help_text)
        import re
        rss_help_text = re.sub(r'<code>(.*?)</code>', ' ', rss_help_text)
        rss_help_text = re.sub('#', '', rss_help_text)

        from bs4 import BeautifulSoup
        rss_help_text = BeautifulSoup(rss_help_text, "lxml").text

        self.hass.states.async_set(
            'sensor.aisrsshelptext', rss_help_text[:200],
            {'text': "" + response.text, 'friendly_name': "Tekst strony"})
        # say only if from remote
        import homeassistant.components.ais_ai_service as ais_ai
        #  binary_sensor.selected_entity / binary_sensor.ais_remote_button
        if ais_ai.CURR_ENTITIE == 'input_select.ais_rss_help_topic' and ais_ai.CURR_BUTTON_CODE == 23:
            self.hass.services.call('ais_ai_service', 'say_it', {"text": "Czytam stronę pomocy. " + rss_help_text})
