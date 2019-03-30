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
GLOBAL_RSS_NEWS_TEXT = None
GLOBAL_RSS_HELP_TEXT = None
G_PLAYERS = []


def get_news_text():
    return GLOBAL_RSS_NEWS_TEXT


def get_rss_help_text():
    return GLOBAL_RSS_HELP_TEXT


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

    def get_radio_types(call):
        _LOGGER.info("get_radio_types  ")
        data.get_radio_types(call)

    def get_radio_names(call):
        _LOGGER.info("get_radio_names")
        data.get_radio_names(call)

    def select_radio_name(call):
        _LOGGER.info("select_radio_name")
        data.select_radio_name(call)

    def get_players(call):
        _LOGGER.info("get_players  ")
        data.get_players(call, hass)

    def play_audio(call):
        _LOGGER.info("play_audio  ")
        data.play_audio(call)

    def get_podcast_types(call):
        _LOGGER.info("get_podcast_types  ")
        data.get_podcast_types(call)

    def get_podcast_names(call):
        _LOGGER.info("get_podcast_names  ")
        data.get_podcast_names(call)

    def get_podcast_tracks(call):
        _LOGGER.info("get_podcast_tracks")
        data.get_podcast_tracks(call)

    def select_podcast_track(call):
        _LOGGER.info("select_podcast_track")
        data.select_podcast_track(call)

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
        _LOGGER.info("get_rss_news_items  ")
        data.get_rss_news_items(call)

    def select_rss_news_item(call):
        _LOGGER.info("select_rss_news_item")
        data.select_rss_news_item(call)

    def select_rss_help_item(call):
        _LOGGER.info("select_rss_help_item")
        data.select_rss_help_item(call)

    # register services
    hass.services.async_register(
        DOMAIN, 'get_radio_types', get_radio_types)
    hass.services.async_register(
        DOMAIN, 'get_radio_names', get_radio_names)
    hass.services.async_register(
        DOMAIN, 'select_radio_name', select_radio_name)
    hass.services.async_register(
        DOMAIN, 'get_players', get_players)
    hass.services.async_register(
        DOMAIN, 'play_audio', play_audio)
    hass.services.async_register(
        DOMAIN, 'get_podcast_types', get_podcast_types)
    hass.services.async_register(
        DOMAIN, 'get_podcast_names', get_podcast_names)
    hass.services.async_register(
        DOMAIN, 'get_podcast_tracks', get_podcast_tracks)
    hass.services.async_register(
        DOMAIN, 'select_podcast_track', select_podcast_track)
    hass.services.async_register(
        DOMAIN, 'select_media_player', select_media_player)
    hass.services.async_register(
        DOMAIN, 'get_rss_news_category', get_rss_news_category)
    hass.services.async_register(
        DOMAIN, 'get_rss_news_channels', get_rss_news_channels)
    hass.services.async_register(
        DOMAIN, 'get_rss_news_items', get_rss_news_items)
    hass.services.async_register(
        DOMAIN, 'select_rss_news_item', select_rss_news_item)
    hass.services.async_register(
        DOMAIN, 'select_rss_help_item', select_rss_help_item)

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
                _old = {}
                _old['friendly_name'] = 'new ais dome device'
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
        # rest_url = self.url + 'ask?question=' + question + " "
        # rest_url += '&org_answer=' + org_answer
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
                # items = data["data"]
                # for item in items:
                #     # values.add(item['type'])
                #     # types = list(sorted(values))
                #     _LOGGER.error("item " + str(item))
        return data

    def store_audio_type(self, nature, json_data):
        path = self.get_path(nature)
        with open(path, 'w') as outfile:
            json.dump(json_data, outfile)

    def audio_name(self, nature, type):
        # get names from cache file
        return None
        # names = [ais_global.G_EMPTY_OPTION]
        # path = self.get_path(nature)
        # if not os.path.isfile(path):
        #     return None
        # else:
        #     return names

    def audio(self, item, type, text_input):
        return None


class AisColudData:
    """Class to hold radio stations data."""

    def __init__(self, hass):
        self.hass = hass
        self.radio_names = []
        self.podcast_names = []
        self.podcast_tracks = []
        self.audio_name = None
        self.cloud = AisCloudWS()
        self.cache = AisCacheData(hass)
        self.news_channels = []
        self.news_items = []

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
        types = [ais_global.G_EMPTY_OPTION]
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
        if call.data["radio_type"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.radio_station_name",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return

        ws_resp = self.cache.audio_name(
            ais_global.G_AN_RADIO, call.data["radio_type"])
        if ws_resp is None:
            ws_resp = self.cloud.audio_name(
                ais_global.G_AN_RADIO, call.data["radio_type"])
        json_ws_resp = ws_resp.json()
        self.radio_names = []
        names = [ais_global.G_EMPTY_OPTION]
        for item in json_ws_resp["data"]:
            names.append(item["NAME"])
            self.radio_names.append(item)
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.radio_station_name",
                "options": names})
        # select the radio name
        if self.audio_name is not None:
            self.hass.block_till_done()
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.radio_station_name",
                    "option": self.audio_name})
            # this name will be set after the list refresh
            self.audio_name = None
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if (ais_ai.CURR_ENTITIE == 'input_select.radio_type'
                and ais_ai.CURR_BUTTON_CODE == 23):
            ais_ai.set_curr_entity(
                self.hass,
                'input_select.radio_station_name')
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Wybierz stację"
                })

    def select_radio_name(self, call):
        """Get station stream url for the selected name."""
        if "radio_name" not in call.data:
            _LOGGER.error("No radio_name")
            return

        # the station was selected from select list in app
        # we need to find the url and play it
        radio_name = call.data["radio_name"]
        _url = None
        _audio_info = {}
        for audio in self.radio_names:
            if audio["NAME"] == radio_name:
                if "STREAM_URL" in audio:
                    _url = check_url(audio["STREAM_URL"])
                    _audio_info["NAME"] = audio["NAME"]
                    _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_RADIO
                    _audio_info["IMAGE_URL"] = audio["IMAGE_URL"]
                    _audio_info = json.dumps(_audio_info)

        if _url is not None:
            # take the entity_id dynamically
            # according to the input_select.radio_player LV
            player_name = self.hass.states.get(
                'input_select.radio_player').state
            player = get_player_data(player_name)
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": check_url(_url)
                })
            # set stream image and title only if the player is AIS dom player
            if player["device_ip"] is not None:
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": player["entity_id"],
                        "media_content_type": "ais_info",
                        "media_content_id": _audio_info
                    })

    def get_podcast_types(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_PODCAST)
        json_ws_resp = ws_resp.json()
        types = [ais_global.G_EMPTY_OPTION]
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
        if call.data["podcast_type"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.podcast_name",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return
        ws_resp = self.cloud.audio_name(
            ais_global.G_AN_PODCAST, call.data["podcast_type"])
        json_ws_resp = ws_resp.json()
        names = [ais_global.G_EMPTY_OPTION]
        self.podcast_names = []
        for item in json_ws_resp["data"]:
            names.append(item["NAME"])
            self.podcast_names.append(item)
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.podcast_name",
                "options": names})
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if (ais_ai.CURR_ENTITIE == 'input_select.podcast_type'
                and ais_ai.CURR_BUTTON_CODE == 23):
            ais_ai.set_curr_entity(
                self.hass,
                'input_select.podcast_name')
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Wybierz audycję"
                })

    def get_podcast_tracks(self, call):
        import feedparser
        if "podcast_name" not in call.data:
            _LOGGER.error("No podcast_name")
            return
        if call.data["podcast_name"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.podcast_track",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return
        podcast_name = call.data["podcast_name"]
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

        if _lookup_url is not None:
            # download the episodes
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Pobieram"
                })
            try:
                d = feedparser.parse(check_url(_lookup_url))
                tracks = [ais_global.G_EMPTY_OPTION]
                self.podcast_tracks = []
                for e in d.entries:
                    track = {'title': e.title, 'link': e.enclosures[0]}
                    try:
                        track['image_url'] = d.feed.image.href
                    except Exception:
                        track['image_url'] = _image_url
                    tracks.append(e.title)
                    self.podcast_tracks.append(track)
                self.hass.services.call(
                    'input_select',
                    'set_options', {
                        "entity_id": "input_select.podcast_track",
                        "options": tracks})

                if selected_by_voice_command:
                    track = self.podcast_tracks[0]
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": "Pobrano " + str(len(d.entries))
                            + " odcinków"
                            + ", audycji " + podcast_name
                            + ", włączam najnowszy odcinek: " + track["title"]
                        })
                    self.hass.services.call(
                        'input_select',
                        'select_option', {
                            "entity_id": "input_select.podcast_track",
                            "option": track["title"]})
                else:
                    # check if the change was done form remote
                    import homeassistant.components.ais_ai_service as ais_ai
                    if (ais_ai.CURR_ENTITIE
                            == 'input_select.podcast_name'
                            and ais_ai.CURR_BUTTON_CODE == 23):
                            ais_ai.set_curr_entity(
                                self.hass,
                                'input_select.podcast_track')
                            self.hass.services.call(
                                'ais_ai_service',
                                'say_it', {
                                    "text": "Pobrano " + str(len(d.entries))
                                    + " odcinków, wybierz odcinek"
                                })
                    else:
                        self.hass.services.call(
                            'ais_ai_service',
                            'say_it', {
                                "text": "Pobrano " + str(len(d.entries))
                                + " odcinków"
                                + ", audycji " + podcast_name
                            })
            except Exception as e:
                _LOGGER.error("Error: " + str(e))
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Nie można pobrać odcinków. " + podcast_name
                    })

    def select_podcast_track(self, call):
        """Get track stream url for the selected name."""
        if "podcast_track" not in call.data:
            _LOGGER.error("No podcast_track")
            return
        if call.data["podcast_track"] == ais_global.G_EMPTY_OPTION:
            # TODO stop selected player
            pass
        # the station was selected from select list in app
        # we need to find the url and play it
        podcast_track = call.data["podcast_track"]
        _url = None
        _audio_info = {}
        for podcast in self.podcast_tracks:
            if podcast["title"] == podcast_track:
                if "link" in podcast:
                    _url = check_url(podcast["link"].href)
                    try:
                        _audio_info["IMAGE_URL"] = podcast["image_url"]
                    except Exception as e:
                        _audio_info["IMAGE_URL"] = ''
                    _audio_info["NAME"] = podcast["title"]
                    _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_PODCAST
                    _audio_info = json.dumps(_audio_info)

        if _url is not None:
            # take the entity_id dynamically
            # according to the input_select.radio_player LV
            player_name = self.hass.states.get(
                'input_select.podcast_player').state
            player = get_player_data(player_name)
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": check_url(_url)
                })
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": _url
                })
            # set stream image and title
            if player["device_ip"] is not None:
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": player["entity_id"],
                        "media_content_type": "ais_info",
                        "media_content_id": _audio_info
                    })

    def play_audio(self, call):
        audio_type = call.data["audio_type"]
        if audio_type == ais_global.G_AN_RADIO:
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.radio_type",
                    "option": call.data["type"]})
            self.hass.block_till_done()
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.radio_station_name",
                    "option": call.data["name"]})
            # this name will be set after the list refresh
            self.audio_name = call.data["name"]
            self.hass.block_till_done()
            player_name = self.hass.states.get(
                'input_select.radio_player').state
            player = get_player_data(player_name)
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": check_url(call.data["stream_url"])
                })
            # set stream image and title
            if player["device_ip"] is not None:
                _audio_info = {"IMAGE_URL": call.data["image_url"], "NAME": call.data["name"],
                               "MEDIA_SOURCE": ais_global.G_AN_RADIO}
                _audio_info = json.dumps(_audio_info)
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": player["entity_id"],
                        "media_content_type": "ais_info",
                        "media_content_id": _audio_info
                    })
        elif audio_type == ais_global.G_AN_PODCAST:
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.podcast_type",
                    "option": call.data["type"]})

            self.hass.services.call(
                'ais_cloud',
                'get_podcast_tracks', {
                    "lookup_url": call.data["lookup_url"],
                    "podcast_name": call.data["name"],
                    "image_url": call.data["image_url"]
                }
            )
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.podcast_name",
                    "option": call.data["name"]})

        elif audio_type == ais_global.G_AN_MUSIC:
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.ais_music_service",
                    "option": "YouTube"})
            # self.hass.block_till_done()
            self.hass.services.call(
                'input_text',
                'set_value', {
                    "entity_id": "input_text.ais_music_query",
                    "value": call.data["text"]})
        elif audio_type == ais_global.G_AN_SPOTIFY:
            self.hass.services.call(
                'input_select',
                'select_option', {
                    "entity_id": "input_select.ais_music_service",
                    "option": ais_global.G_AN_SPOTIFY})
            # self.hass.block_till_done()
            self.hass.services.call(
                'input_text',
                'set_value', {
                    "entity_id": "input_text.ais_music_query",
                    "value": call.data["text"] + " "})

    def select_media_player(self, call):
        if "media_player_type" not in call.data:
            _LOGGER.error("No media_player_type")
            return
        player_name = None
        _url = None
        _audio_info = {}
        media_player_type = call.data["media_player_type"]
        if media_player_type == "Radio":
            radio_name = self.hass.states.get(
                'input_select.radio_station_name').state
            if radio_name == ais_global.G_EMPTY_OPTION:
                return
            player_name = self.hass.states.get(
                'input_select.radio_player').state
            for radio in self.radio_names:
                if radio["NAME"] == radio_name:
                    if "STREAM_URL" in radio:
                        _url = radio["STREAM_URL"]
                        _audio_info["NAME"] = radio["NAME"]
                        _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_RADIO
                        _audio_info["IMAGE_URL"] = radio["IMAGE_URL"]
        if media_player_type == "Podcast":
            podcast_track = self.hass.states.get(
                'input_select.podcast_track').state
            if podcast_track == ais_global.G_EMPTY_OPTION:
                return
            player_name = self.hass.states.get(
                'input_select.podcast_player').state
            for track in self.podcast_tracks:
                if track["title"] == podcast_track:
                    if "link" in track:
                        _url = track["link"].href
                        try:
                            _audio_info["IMAGE_URL"] = track["image_url"]
                        except Exception as e:
                            _audio_info["IMAGE_URL"] = ''
                        _audio_info["NAME"] = track["title"]
                        _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_PODCAST
        if media_player_type == "Music":
            track_name = self.hass.states.get(
                'input_select.ais_music_track_name').state
            if track_name == ais_global.G_EMPTY_OPTION:
                return
            player_name = self.hass.states.get(
                'input_select.ais_music_player').state
            import homeassistant.components.ais_yt_service as yt
            for music_track in yt.G_YT_FOUND:
                if music_track["title"] == track_name:
                    _url = "https://www.youtube.com/watch?v="
                    _url += music_track["id"]
                    _audio_info["IMAGE_URL"] = music_track["thumbnail"]
                    _audio_info["NAME"] = music_track["title"]
                    _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_MUSIC
        if media_player_type == "Book":
            chapter_name = self.hass.states.get(
                'input_select.book_chapter').state
            if chapter_name == ais_global.G_EMPTY_OPTION:
                return
            player_name = self.hass.states.get(
                'input_select.book_player').state
            import homeassistant.components.ais_gm_service as gm
            for ch in gm.G_SELECTED_TRACKS:
                if ch["name"] == chapter_name:
                    _url = gm.G_GM_MOBILE_CLIENT_API.get_stream_url(ch["id"])
                    _audio_info = {"IMAGE_URL": ch["image"], "NAME": ch["name"],
                                   "MEDIA_SOURCE": ais_global.G_AN_AUDIOBOOK}
        if player_name is not None:
            player = get_player_data(player_name)
        if _url is not None:
            # play media on selected device
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": check_url(_url)
                })
            if player["device_ip"] is not None:
                # set stream image and title
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": player["entity_id"],
                        "media_content_type": "ais_info",
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

        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.radio_player",
                    "options": players_lv}))
        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.podcast_player",
                    "options": players_lv}))
        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.ais_music_player",
                    "options": players_lv}))
        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.book_player",
                    "options": players_lv}))
        hass.async_add_job(
            hass.services.async_call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.rss_news_player",
                    "options": players_lv}))
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
        if (ais_ai.CURR_ENTITIE == 'input_select.rss_news_category'
                and ais_ai.CURR_BUTTON_CODE == 23):
            ais_ai.set_curr_entity(
                self.hass,
                'input_select.rss_news_channel')
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Wybierz kanał wiadomości"
                })

    def get_rss_news_items(self, call):
        import feedparser
        if "rss_news_channel" not in call.data:
            _LOGGER.error("No rss_news_channel")
            return
        if call.data["rss_news_channel"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.rss_news_item",
                    "options": [ais_global.G_EMPTY_OPTION]})
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

        if _lookup_url is not None:
            # download the episodes
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "pobieram"
                })
            try:
                d = feedparser.parse(_lookup_url)
                items = [ais_global.G_EMPTY_OPTION]
                self.news_items = []
                for e in d.entries:
                    item = {'title': e.title, 'link': e.link, 'image_url': _image_url, 'description': e.description}
                    if e.title not in items:
                        items.append(e.title)
                        self.news_items.append(item)
                self.hass.services.call(
                    'input_select',
                    'set_options', {
                        "entity_id": "input_select.rss_news_item",
                        "options": items})

                if selected_by_voice_command:
                    item = self.news_items[0]
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": "mamy "
                            + str(len(d.entries)) + " wiadomości z "
                            + rss_news_channel
                            + ", czytam najnowszy artykuł: " + item["title"]
                        })
                    self.hass.services.call(
                        'input_select',
                        'select_option', {
                            "entity_id": "input_select.rss_news_item",
                            "option": item["title"]})

                else:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": "mamy "
                            + str(len(d.entries))
                            + " wiadomości, wybierz artykuł"
                        })
                    # check if the change was done form remote
                    import homeassistant.components.ais_ai_service as ais_ai
                    if (ais_ai.CURR_ENTITIE
                            == 'input_select.rss_news_channel'
                            and ais_ai.CURR_BUTTON_CODE == 23):
                                ais_ai.set_curr_entity(
                                    self.hass,
                                    'input_select.rss_news_item')

            except Exception as e:
                _LOGGER.error("Error: " + str(e))
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Nie można pobrać wiadomości z: "
                                + rss_news_channel
                    })

    def select_rss_news_item(self, call):
        """Get text for the selected item."""
        global GLOBAL_RSS_NEWS_TEXT
        if "rss_news_item" not in call.data:
            _LOGGER.error("No rss_news_item")
            return
        if call.data["rss_news_item"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            GLOBAL_RSS_NEWS_TEXT = ''
            self.hass.states.async_set(
                'sensor.rss_news_text', '-', {
                    'text': "" + GLOBAL_RSS_NEWS_TEXT,
                    'friendly_name': 'Tekst strony'
                    })
            return
        # the station was selected from select list in app
        # we need to find the url and read the text
        rss_news_item = call.data["rss_news_item"]
        _url = None
        for item in self.news_items:
            if item["title"] == rss_news_item:
                if "description" in item:
                    GLOBAL_RSS_NEWS_TEXT = item["description"]
                if "link" in item:
                    _url = check_url(item["link"])

        if _url is not None:
            import requests
            from readability import Document
            response = requests.get(check_url(_url), timeout=5)
            response.encoding = 'utf-8'
            doc = Document(response.text)
            GLOBAL_RSS_NEWS_TEXT += doc.summary()

        from bs4 import BeautifulSoup
        GLOBAL_RSS_NEWS_TEXT = BeautifulSoup(
            GLOBAL_RSS_NEWS_TEXT, "lxml").text

        text = "Czytam artykuł. " + GLOBAL_RSS_NEWS_TEXT
        self.hass.services.call(
            'ais_ai_service',
            'say_it', {
                "text": text
            })
        self.hass.states.async_set(
            'sensor.rss_news_text', GLOBAL_RSS_NEWS_TEXT[:200], {
                'text': "" + GLOBAL_RSS_NEWS_TEXT,
                'friendly_name': 'Tekst strony'
                })

    def select_rss_help_item(self, call):
        """Get text for the selected item."""
        global GLOBAL_RSS_HELP_TEXT
        GLOBAL_RSS_HELP_TEXT = ''
        if "rss_help_topic" not in call.data:
            _LOGGER.error("No rss_help_topic")
            return
        if call.data["rss_help_topic"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.states.async_set(
                'sensor.ais_rss_help_text', "-", {
                    'text': "" + GLOBAL_RSS_HELP_TEXT,
                    'friendly_name': "Tekst strony"
                })
            return
        # we need to build the url and get the text to read
        rss_help_topic = call.data["rss_help_topic"]
        _url = check_url(
            "https://raw.githubusercontent.com/wiki/sviete/AIS-WWW/" + rss_help_topic.replace(" ", "-") + ".md")
        import requests
        from readability import Document

        response = requests.get(_url, timeout=5)
        doc = Document(response.text)
        GLOBAL_RSS_HELP_TEXT += doc.summary()

        from markdown import markdown
        GLOBAL_RSS_HELP_TEXT = markdown(GLOBAL_RSS_HELP_TEXT)
        import re
        GLOBAL_RSS_HELP_TEXT = re.sub(r'<code>(.*?)</code>', ' ', GLOBAL_RSS_HELP_TEXT)
        GLOBAL_RSS_HELP_TEXT = re.sub('#', '', GLOBAL_RSS_HELP_TEXT)

        from bs4 import BeautifulSoup
        GLOBAL_RSS_HELP_TEXT = BeautifulSoup(
            GLOBAL_RSS_HELP_TEXT, "lxml").text

        text = "Czytam stronę pomocy. " + GLOBAL_RSS_HELP_TEXT
        self.hass.services.call(
            'ais_ai_service',
            'say_it', {
                "text": text
            })
        self.hass.states.async_set(
            'sensor.ais_rss_help_text', GLOBAL_RSS_HELP_TEXT[:200], {
                'text': "" + response.text,
                'friendly_name': "Tekst strony"
            })
