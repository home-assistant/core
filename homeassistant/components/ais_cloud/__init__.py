"""Component to manage the AIS Cloud."""
import asyncio
import json
import logging
import os

import async_timeout
import requests

from homeassistant.components.ais_dom import ais_global
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    EVENT_PLATFORM_DISCOVERED,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util import slugify

DOMAIN = "ais_cloud"
_LOGGER = logging.getLogger(__name__)
CLOUD_APP_URL = "https://powiedz.co/ords/f?p=100:1&x01=TOKEN:"
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


async def async_setup(hass, config):
    """Initialize the radio station list."""
    data = hass.data[DOMAIN] = AisColudData(hass)
    await data.async_get_types()
    #
    hass.states.async_set("sensor.radiolist", -1, {})
    hass.states.async_set("sensor.podcastlist", -1, {})
    hass.states.async_set("sensor.podcastnamelist", -1, {})
    hass.states.async_set("sensor.youtubelist", -1, {})
    hass.states.async_set("sensor.spotifysearchlist", -1, {})
    hass.states.async_set("sensor.spotifylist", -1, {})
    hass.states.async_set("sensor.rssnewslist", -1, {})
    hass.states.async_set("sensor.audiobookslist", -1, {})
    hass.states.async_set("sensor.audiobookschapterslist", -1, {})
    hass.states.async_set("sensor.rssnewstext", "", {"text": ""})
    hass.states.async_set("sensor.aisrsshelptext", "", {"text": ""})
    hass.states.async_set("sensor.aisknowledgeanswer", "", {"text": ""})

    def get_radio_types(call):
        data.get_radio_types(call)

    def get_radio_names(call):
        data.get_radio_names(call)

    def get_players(call):
        data.get_players(call, hass)

    def play_audio(call):
        data.process_play_audio(call)

    def delete_audio(call):
        data.process_delete_audio(call)

    def get_podcast_types(call):
        data.get_podcast_types(call)

    def get_podcast_names(call):
        data.get_podcast_names(call)

    def get_podcast_tracks(call):
        data.get_podcast_tracks(call)

    def get_rss_news_category(call):
        data.get_rss_news_category(call)

    def get_rss_news_channels(call):
        data.get_rss_news_channels(call)

    def get_rss_news_items(call):
        data.get_rss_news_items(call)

    def select_rss_news_item(call):
        data.select_rss_news_item(call)

    def get_backup_info(call):
        data.get_backup_info(call)

    def set_backup_step(call):
        data.set_backup_step(call)

    def restore_backup(call):
        data.restore_backup(call)

    def do_backup(call):
        data.do_backup(call)

    def select_rss_help_item(call):
        data.select_rss_help_item(call)

    def play_prev(call):
        data.play_prev(call)

    def play_next(call):
        data.play_next(call)

    def change_audio_service(call):
        data.change_audio_service(call)

    def send_audio_to_speaker(call):
        data.send_audio_to_speaker(call)

    def enable_gate_pairing_by_pin(call):
        data.enable_gate_pairing_by_pin(call)

    # register services
    hass.services.async_register(DOMAIN, "get_radio_types", get_radio_types)
    hass.services.async_register(DOMAIN, "get_radio_names", get_radio_names)
    hass.services.async_register(DOMAIN, "get_players", get_players)
    hass.services.async_register(DOMAIN, "play_audio", play_audio)
    hass.services.async_register(DOMAIN, "delete_audio", delete_audio)
    hass.services.async_register(DOMAIN, "get_podcast_types", get_podcast_types)
    hass.services.async_register(DOMAIN, "get_podcast_names", get_podcast_names)
    hass.services.async_register(DOMAIN, "get_podcast_tracks", get_podcast_tracks)
    hass.services.async_register(DOMAIN, "get_rss_news_category", get_rss_news_category)
    hass.services.async_register(DOMAIN, "get_rss_news_channels", get_rss_news_channels)
    hass.services.async_register(DOMAIN, "get_rss_news_items", get_rss_news_items)
    hass.services.async_register(DOMAIN, "select_rss_news_item", select_rss_news_item)
    hass.services.async_register(DOMAIN, "select_rss_help_item", select_rss_help_item)
    hass.services.async_register(DOMAIN, "play_prev", play_prev)
    hass.services.async_register(DOMAIN, "play_next", play_next)
    hass.services.async_register(DOMAIN, "change_audio_service", change_audio_service)
    hass.services.async_register(DOMAIN, "send_audio_to_speaker", send_audio_to_speaker)
    hass.services.async_register(DOMAIN, "get_backup_info", get_backup_info)
    hass.services.async_register(DOMAIN, "set_backup_step", set_backup_step)
    hass.services.async_register(DOMAIN, "do_backup", do_backup)
    hass.services.async_register(DOMAIN, "restore_backup", restore_backup)
    hass.services.async_register(
        DOMAIN, "enable_gate_pairing_by_pin", enable_gate_pairing_by_pin
    )

    def device_discovered(service):
        """ Called when a device has been discovered. """
        if ais_global.G_AIS_START_IS_DONE:
            _LOGGER.info("Discovered a new device type: " + str(service.as_dict()))
            try:
                d = service.as_dict().get("data")
                s = d.get("service")
                p = d.get("platform")
                if s == "load_platform.sensor" and p == "mqtt":
                    i = d.get("discovered")
                    uid = i.get("unique_id")
                    if uid is not None:
                        # search entity_id for this unique_id - add sensor to group
                        if hass.services.has_service("group", "set"):
                            hass.async_add_job(
                                hass.services.async_call(
                                    "group",
                                    "set",
                                    {
                                        "object_id": "all_ais_sensors",
                                        "add_entities": ["sensor." + uid],
                                    },
                                )
                            )
                elif s == "load_platform.media_player":
                    hass.async_add_job(
                        hass.services.async_call("ais_cloud", "get_players")
                    )

                _LOGGER.info("Discovered device prepare remote menu!")
                # prepare menu
                hass.async_add_job(
                    hass.services.async_call("ais_ai_service", "prepare_remote_menu")
                )
            except Exception as e:
                _LOGGER.error("device_discovered: " + str(e))

    hass.bus.async_listen(EVENT_PLATFORM_DISCOVERED, device_discovered)

    def state_changed(state_event):
        """ Called on state change """
        if ais_global.G_AIS_START_IS_DONE is False:
            return

        entity_id = state_event.data.get("entity_id")
        if entity_id == "input_select.assistant_voice":
            # old_voice = state_event.data["old_state"].state
            new_voice = state_event.data["new_state"].state
            if new_voice == "Jola online":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda-network"
            elif new_voice == "Jola lokalnie":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda-local"
            elif new_voice == "Celina":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#female_1-local"
            elif new_voice == "Anżela":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#female_2-local"
            elif new_voice == "Asia":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#female_3-local"
            elif new_voice == "Sebastian":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#male_1-local"
            elif new_voice == "Bartek":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#male_2-local"
            elif new_voice == "Andrzej":
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda#male_3-local"
            else:
                ais_global.GLOBAL_TTS_VOICE = "pl-pl-x-oda-local"
            # publish to frame
            if ais_global.G_AIS_START_IS_DONE:
                hass.services.call("ais_ai_service", "say_it", {"text": new_voice})
            hass.services.call(
                "ais_ai_service",
                "publish_command_to_frame",
                {"key": "setTtsVoice", "val": ais_global.GLOBAL_TTS_VOICE},
            )
        elif entity_id == "input_number.assistant_rate":
            try:
                ais_global.GLOBAL_TTS_RATE = float(hass.states.get(entity_id).state)
            except Exception:
                ais_global.GLOBAL_TTS_RATE = 1
        elif entity_id == "input_number.assistant_tone":
            try:
                ais_global.GLOBAL_TTS_PITCH = float(hass.states.get(entity_id).state)
            except Exception:
                ais_global.GLOBAL_TTS_PITCH = 1
        elif entity_id == "input_select.ais_android_wifi_network":
            # take the password for wifi if value changed
            if state_event.data["old_state"] is not None:
                _old_state = state_event.data["old_state"].state
                _new_state = state_event.data["new_state"].state
                if _old_state != _new_state:
                    ssid = hass.states.get(
                        "input_select.ais_android_wifi_network"
                    ).state.split(";")[0]
                    password = ais_global.get_pass_for_ssid(ssid)
                    hass.services.call(
                        "input_text",
                        "set_value",
                        {
                            "value": password,
                            "entity_id": "input_text.ais_iot_device_wifi_password",
                        },
                    )
        elif entity_id in (
            "input_boolean.ais_quiet_mode",
            "input_datetime.ais_quiet_mode_start",
            "input_datetime.ais_quiet_mode_stop",
        ):
            hass.async_add_job(
                hass.services.async_call(
                    "ais_ai_service", "check_night_mode", {"timer": False}
                )
            )

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)
    return True


class AisCloudWS:
    def __init__(self, hass):
        """Initialize the cloud WS connections."""
        self.url = "https://powiedz.co/ords/dom/dom/"
        self.url_gh = "https://powiedz.co/ords/dom/gh/"
        self.hass = hass
        self.cloud_ws_token = ais_global.get_sercure_android_id_dom()
        self.cloud_ws_header = {"Authorization": f"{self.cloud_ws_token}"}

    def gh_ais_add_device(self, oauth_json):
        payload = {
            "user": ais_global.get_sercure_android_id_dom(),
            "oauthJson": oauth_json,
        }
        ws_resp = requests.post(
            self.url_gh + "ais_add_device",
            json=payload,
            headers=self.cloud_ws_header,
            timeout=5,
        )
        return ws_resp

    def gh_ais_add_token(self, oauth_code):
        payload = {
            "user": ais_global.get_sercure_android_id_dom(),
            "oauthCode": oauth_code,
        }
        ws_resp = requests.post(
            self.url_gh + "ais_add_token",
            json=payload,
            headers=self.cloud_ws_header,
            timeout=5,
        )
        return ws_resp

    def gh_ais_remove_integration(self):
        payload = {"user": ais_global.get_sercure_android_id_dom()}
        ws_resp = requests.post(
            self.url_gh + "ais_remove_integration",
            json=payload,
            headers=self.cloud_ws_header,
            timeout=5,
        )
        return ws_resp

    async def async_ask_json_gh(self, question, hass):
        web_session = aiohttp_client.async_get_clientsession(hass)
        payload = {
            "command": question,
            "user": ais_global.get_sercure_android_id_dom(),
            "broadcast": False,
            "converse": True,
        }
        with async_timeout.timeout(5):
            ws_resp = await web_session.post(
                self.url_gh + "ask_json", json=payload, headers=self.cloud_ws_header
            )
            return await ws_resp.json()

    def ask(self, question, org_answer):
        payload = {"question": question, "org_answer": org_answer}
        ws_resp = requests.get(
            self.url + "ask", headers=self.cloud_ws_header, params=payload, timeout=5
        )
        return ws_resp

    def audio_type(self, nature):
        try:
            rest_url = self.url + "audio_type?nature=" + nature
            ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=5)
            return ws_resp
        except:
            _LOGGER.error("Can't connect to AIS WS!!! " + rest_url)
            ais_global.G_OFFLINE_MODE = True

    def audio_name(self, nature, a_type):
        rest_url = self.url + "audio_name?nature=" + nature
        rest_url += "&type=" + a_type
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp

    def audio(self, item, a_type, text_input):
        rest_url = self.url + "audio?item=" + item + "&type="
        rest_url += a_type + "&text_input=" + text_input
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp

    def key(self, service):
        rest_url = self.url + "key?service=" + service
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp.json()

    async def async_key(self, service):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        rest_url = self.url + "key?service=" + service
        try:
            # during the system start lot of things is done 300 sec should be enough
            with async_timeout.timeout(300):
                ws_resp = await web_session.get(rest_url, headers=self.cloud_ws_header)
                return await ws_resp.json()
        except Exception as e:
            _LOGGER.error("Couldn't fetch data for: " + service + " " + str(e))
            # import traceback
            # traceback.print_exc()

    async def async_new_key(self, service, old_key):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        rest_url = self.url + "new_key?service=" + service + "&old_key=" + old_key
        with async_timeout.timeout(10):
            ws_resp = await web_session.get(rest_url, headers=self.cloud_ws_header)
            return await ws_resp.json()

    def extract_media(self, url, local_extractor_version):
        rest_url = (
            self.url
            + "extract_media?url="
            + url
            + "&extractor_version="
            + local_extractor_version
        )
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=10)
        return ws_resp

    def delete_key(self, service):
        rest_url = self.url + "key?service=" + service
        ws_resp = requests.delete(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp

    def get_backup_info(self):
        rest_url = self.url + "backup_info"
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp

    def post_backup(self, file, backup_type):
        if backup_type == "ha":
            rest_url = self.url + "backup"
        elif backup_type == "zigbee":
            rest_url = self.url + "backup_zigbee"
        elif backup_type == "zwave":
            rest_url = self.url + "backup_zwave"
        with open(file, "rb") as payload:
            ws_resp = requests.post(
                rest_url, headers=self.cloud_ws_header, data=payload, timeout=60
            )
        return ws_resp

    def download_backup(self, file, backup_type):
        if backup_type == "ha":
            rest_url = self.url + "backup"
        elif backup_type == "zigbee":
            rest_url = self.url + "backup_zigbee"
        elif backup_type == "zwave":
            rest_url = self.url + "backup_zwave"
        ws_resp = requests.get(rest_url, headers=self.cloud_ws_header, timeout=60)
        with open(file, "wb") as f:
            for chunk in ws_resp.iter_content(1024):
                f.write(chunk)
        return ws_resp

    def get_gate_parring_pin(self):
        rest_url = self.url + "gate_id_from_pin"
        ws_resp = requests.post(rest_url, headers=self.cloud_ws_header, timeout=5)
        return ws_resp


class AisCacheData:
    def __init__(self, hass):
        """Initialize the files cache"""
        self.hass = hass
        self.persistence_radio = "/dom/radio_stations.json"
        self.persistence_podcast = "/dom/podcast.json"
        self.persistence_news = "/dom/news_chanels.json"

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
        with open(path, "w") as outfile:
            json.dump(json_data, outfile)

    def audio(self, item, type, text_input):
        return None


class AisColudData:
    """Class to hold radio stations data."""

    def __init__(self, hass):
        self.hass = hass
        self.audio_name = None
        self.cloud = AisCloudWS(hass)
        self.cache = AisCacheData(hass)
        self.news_channels = []

    async def async_get_types(self):
        # check if we have data stored in local files
        # otherwise we should work in online mode and get data from cloud
        # ----------------
        # ----- RADIO ----
        # ----------------
        ws_resp = self.cloud.audio_type(ais_global.G_AN_RADIO)
        try:
            json_ws_resp = ws_resp.json()
            self.cache.store_audio_type(ais_global.G_AN_RADIO, json_ws_resp)
            types = [ais_global.G_EMPTY_OPTION]
        except Exception as e:
            _LOGGER.error("RADIO WS resp " + str(ws_resp) + " " + str(e))

        # ----------------
        # --- PODCASTS ---
        # ----------------
        ws_resp = self.cloud.audio_type(ais_global.G_AN_PODCAST)
        try:
            json_ws_resp = ws_resp.json()
            self.cache.store_audio_type(ais_global.G_AN_PODCAST, json_ws_resp)
            types = [ais_global.G_EMPTY_OPTION]
        except Exception as e:
            _LOGGER.error("PODCASTS WS resp " + str(ws_resp) + " " + str(e))

        # ----------------
        # ----- NEWS -----
        # ----------------
        ws_resp = self.cloud.audio_type(ais_global.G_AN_NEWS)
        try:
            json_ws_resp = ws_resp.json()
            self.cache.store_audio_type(ais_global.G_AN_NEWS, json_ws_resp)
            types = [ais_global.G_EMPTY_OPTION]
        except Exception as e:
            _LOGGER.error("NEWS WS resp " + str(ws_resp) + " " + str(e))

    def get_radio_types(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_RADIO)
        json_ws_resp = ws_resp.json()
        types = [ais_global.G_FAVORITE_OPTION]
        for item in json_ws_resp["data"]:
            types.append(item)
        # populate list with all stations from selected type
        self.hass.services.call(
            "input_select",
            "set_options",
            {"entity_id": "input_select.radio_type", "options": types},
        )

    def get_radio_names(self, call):
        """Load stations of the for the selected type."""
        if "radio_type" not in call.data:
            return []

        if call.data["radio_type"] == ais_global.G_FAVORITE_OPTION:
            # get radio stations from favorites
            self.hass.services.call(
                "ais_bookmarks",
                "get_favorites",
                {"audio_source": ais_global.G_AN_RADIO},
            )
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
            list_info[list_idx]["icon"] = "mdi:play"
            list_idx = list_idx + 1

        # create lists
        self.hass.states.async_set("sensor.radiolist", -1, list_info)

        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai

        if (
            ais_ai.CURR_ENTITIE == "input_select.radio_type"
            and ais_ai.CURR_BUTTON_CODE == 23
        ):
            ais_ai.set_curr_entity(self.hass, "sensor.radiolist")
            self.hass.services.call(
                "ais_ai_service", "say_it", {"text": "Wybierz stację"}
            )

    def get_podcast_types(self, call):
        ws_resp = self.cloud.audio_type(ais_global.G_AN_PODCAST)
        json_ws_resp = ws_resp.json()
        types = [ais_global.G_FAVORITE_OPTION]
        for item in json_ws_resp["data"]:
            types.append(item)
        # populate list with all podcast types
        self.hass.services.call(
            "input_select",
            "set_options",
            {"entity_id": "input_select.podcast_type", "options": types},
        )

    def get_podcast_names(self, call):
        """Load podcasts names for the selected type."""
        if "podcast_type" not in call.data:
            return []
        if call.data["podcast_type"] == ais_global.G_FAVORITE_OPTION:
            # get podcasts from favorites
            self.hass.services.call(
                "ais_bookmarks",
                "get_favorites",
                {"audio_source": ais_global.G_AN_PODCAST},
            )
            return
        ws_resp = self.cloud.audio_name(
            ais_global.G_AN_PODCAST, call.data["podcast_type"]
        )
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
            list_info[list_idx]["icon"] = "mdi:podcast"
            list_idx = list_idx + 1

        # create lists
        self.hass.states.async_set("sensor.podcastnamelist", -1, list_info)

        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai

        if (
            ais_ai.CURR_ENTITIE == "input_select.podcast_type"
            and ais_ai.CURR_BUTTON_CODE == 23
        ):
            ais_ai.set_curr_entity(self.hass, "sensor.podcastnamelist")
            self.hass.services.call(
                "ais_ai_service", "say_it", {"text": "Wybierz audycję"}
            )

    def get_podcast_tracks(self, call):
        import feedparser
        import io
        import homeassistant.components.ais_ai_service as ais_ai

        selected_by_remote = False
        if (
            ais_ai.CURR_ENTITIE == "sensor.podcastnamelist"
            and ais_ai.CURR_BUTTON_CODE == 23
        ):
            selected_by_remote = True
        if "podcast_name" not in call.data:
            return
        if call.data["podcast_name"] == ais_global.G_FAVORITE_OPTION:
            # get podcasts from favorites
            self.hass.services.call(
                "ais_bookmarks",
                "get_favorites",
                {"audio_source": ais_global.G_AN_PODCAST},
            )
            return

        podcast_name = call.data["podcast_name"]
        self.hass.services.call(
            "ais_ai_service",
            "say_it",
            {"text": "Pobieram odcinki audycji " + podcast_name},
        )
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
                        "ais_ai_service",
                        "say_it",
                        {
                            "text": "Nie można pobrać odcinków. Brak odpowiedzi z "
                            + podcast_name
                        },
                    )
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
                    list_info[list_idx]["icon"] = "mdi:play"
                    list_info[list_idx]["lookup_url"] = _lookup_url
                    list_info[list_idx]["lookup_name"] = podcast_name
                    list_idx = list_idx + 1

                # update list
                self.hass.states.async_set("sensor.podcastlist", -1, list_info)
                if selected_by_voice_command:
                    self.hass.services.call(
                        "ais_ai_service",
                        "say_it",
                        {
                            "text": "Pobrano "
                            + str(len(d.entries))
                            + " odcinków"
                            + ", audycji "
                            + podcast_name
                            + ", włączam najnowszy odcinek: "
                            + list_info[0]["title"]
                        },
                    )
                    # play it
                    self.hass.services.call(
                        "ais_cloud",
                        "play_audio",
                        {
                            "id": 0,
                            "media_source": ais_global.G_AN_PODCAST,
                            "lookup_url": _lookup_url,
                            "lookup_name": podcast_name,
                        },
                    )
                else:
                    # check if the change was done form remote
                    if selected_by_remote:
                        if len(d.entries) > 0:
                            ais_ai.set_curr_entity(self.hass, "sensor.podcastlist")
                            self.hass.services.call(
                                "ais_ai_service",
                                "say_it",
                                {
                                    "text": "Pobrano "
                                    + str(len(d.entries))
                                    + " odcinków, wybierz odcinek"
                                },
                            )
                        else:
                            self.hass.services.call(
                                "ais_ai_service", "say_it", {"text": "Brak odcinków"}
                            )
                    else:
                        self.hass.services.call(
                            "ais_ai_service",
                            "say_it",
                            {
                                "text": "Pobrano "
                                + str(len(d.entries))
                                + " odcinków"
                                + ", audycji "
                                + podcast_name
                            },
                        )
            except Exception as e:
                _LOGGER.error("Error: " + str(e))
                self.hass.services.call(
                    "ais_ai_service",
                    "say_it",
                    {"text": "Nie można pobrać odcinków. " + podcast_name},
                )

    def process_delete_audio(self, call):
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_FAVORITE:
            self.hass.services.call(
                "ais_bookmarks", "delete_favorite", {"id": call.data["id"]}
            )
        elif media_source == ais_global.G_AN_BOOKMARK:
            self.hass.services.call(
                "ais_bookmarks", "delete_bookmark", {"id": call.data["id"]}
            )
        elif media_source == ais_global.G_AN_MUSIC:
            """Delete selected musoc"""
            track_id = int(call.data.get("id"))
            state = self.hass.states.get("sensor.youtubelist")
            attr = state.attributes
            state = state.state
            new_attr = {}
            list_idx = -1
            for itm in attr:
                if not itm == track_id:
                    list_idx = list_idx + 1
                    new_attr[list_idx] = attr[itm]
            self.hass.states.async_set("sensor.youtubelist", state, new_attr)

        elif media_source == ais_global.G_AN_SPOTIFY_SEARCH:
            track_id = int(call.data.get("id"))
            state = self.hass.states.get("sensor.spotifysearchlist")
            attr = state.attributes
            state = state.state
            new_attr = {}
            list_idx = -1
            for itm in attr:
                if not itm == track_id:
                    list_idx = list_idx + 1
                    new_attr[list_idx] = attr[itm]
            self.hass.states.async_set("sensor.spotifysearchlist", state, new_attr)
        elif media_source == ais_global.G_AN_SPOTIFY:
            track_id = int(call.data.get("id"))
            state = self.hass.states.get("sensor.spotifylist")
            attr = state.attributes
            state = state.state
            new_attr = {}
            list_idx = -1
            for itm in attr:
                if not itm == track_id:
                    list_idx = list_idx + 1
                    new_attr[list_idx] = attr[itm]
            self.hass.states.async_set("sensor.spotifylist", state, new_attr)

    def process_play_audio(self, call):
        media_source = call.data["media_source"]
        if "id" in call.data:
            if media_source == ais_global.G_AN_SPOTIFY_SEARCH:
                self.hass.services.call(
                    "ais_spotify_service", "select_search_uri", {"id": call.data["id"]}
                )
                return
            elif media_source == ais_global.G_AN_SPOTIFY:
                self.hass.services.call(
                    "ais_spotify_service", "select_track_uri", {"id": call.data["id"]}
                )
                return
            elif media_source == ais_global.G_AN_MUSIC:
                self.hass.services.call(
                    "ais_yt_service", "select_track_uri", {"id": call.data["id"]}
                )
                return
            elif media_source == ais_global.G_AN_AUDIOBOOK:
                self.hass.services.call(
                    "ais_audiobooks_service", "get_chapters", {"id": call.data["id"]}
                )
                return
            elif media_source == ais_global.G_AN_AUDIOBOOK_CHAPTER:
                self.hass.services.call(
                    "ais_audiobooks_service", "select_chapter", {"id": call.data["id"]}
                )
                return
            #
            if media_source == ais_global.G_AN_RADIO:
                track_list = "sensor.radiolist"
            elif media_source == ais_global.G_AN_PODCAST:
                track_list = "sensor.podcastlist"
            elif media_source == ais_global.G_AN_NEWS:
                track_list = "sensor.rssnewslist"
            elif media_source == ais_global.G_AN_AUDIOBOOK:
                track_list = "sensor.audiobookslist"
            elif media_source == ais_global.G_AN_AUDIOBOOK_CHAPTER:
                track_list = "sensor.audiobookschapterslist"
            elif media_source == ais_global.G_AN_BOOKMARK:
                track_list = "sensor.aisbookmarkslist"
            elif media_source == ais_global.G_AN_FAVORITE:
                track_list = "sensor.aisfavoriteslist"
            elif media_source == ais_global.G_AN_PODCAST_NAME:
                track_list = "sensor.podcastnamelist"

            state = self.hass.states.get(track_list)
            attr = state.attributes
            track = attr.get(int(call.data["id"]))

            if media_source == ais_global.G_AN_NEWS:
                self.hass.services.call(
                    "ais_cloud", "select_rss_news_item", {"id": call.data["id"]}
                )

            elif (
                media_source in (ais_global.G_AN_PODCAST_NAME, ais_global.G_AN_FAVORITE)
                and track["audio_type"] == ais_global.G_AN_PODCAST
            ):
                # selected from favorite - get the podcast tracks
                self.hass.services.call(
                    "ais_cloud",
                    "get_podcast_tracks",
                    {
                        "lookup_url": track["uri"],
                        "podcast_name": track["name"],
                        "image_url": track["thumbnail"],
                        "media_source": ais_global.G_AN_FAVORITE,
                    },
                )
            elif (
                media_source == ais_global.G_AN_FAVORITE
                and track["audio_type"] == ais_global.G_AN_MUSIC
            ):
                # selected from favorite - get the yt url
                self.hass.services.call(
                    "ais_yt_service",
                    "select_track_uri",
                    {"id": call.data["id"], "media_source": ais_global.G_AN_FAVORITE},
                )

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
                self.hass.states.async_set(track_list, call.data["id"], attr)
                # set stream uri, image and title
                _audio_info = json.dumps(
                    {
                        "IMAGE_URL": track["thumbnail"],
                        "NAME": track["title"],
                        "MEDIA_SOURCE": media_source,
                        "media_content_id": track_uri,
                        "lookup_url": lookup_url,
                        "lookup_name": lookup_name,
                        "audio_type": track["audio_type"],
                    }
                )
                self.hass.services.call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                        "media_content_type": "ais_content_info",
                        "media_content_id": _audio_info,
                    },
                )
                return
            elif media_source == ais_global.G_AN_BOOKMARK:
                self.hass.states.async_set(track_list, call.data["id"], attr)
                self.hass.services.call(
                    "ais_bookmarks", "play_bookmark", {"id": call.data["id"]}
                )
                return
            elif media_source == ais_global.G_AN_FAVORITE:
                self.hass.states.async_set(track_list, call.data["id"], attr)
                self.hass.services.call(
                    "ais_bookmarks", "play_favorite", {"id": call.data["id"]}
                )
                return

        else:
            # play by voice
            if media_source == ais_global.G_AN_RADIO:
                # set stream uri, image and title
                _audio_info = {
                    "IMAGE_URL": call.data["image_url"],
                    "NAME": call.data["name"],
                    "MEDIA_SOURCE": ais_global.G_AN_RADIO,
                    "media_content_id": check_url(call.data["stream_url"]),
                }
                _audio_info = json.dumps(_audio_info)
                self.hass.services.call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                        "media_content_type": "ais_content_info",
                        "media_content_id": _audio_info,
                    },
                )

                # switch UI to Radio
                self.hass.services.call(
                    "ais_ai_service", "switch_ui", {"mode": "Radio"}
                )

                #  get list
                self.hass.services.call(
                    "input_select",
                    "select_option",
                    {
                        "entity_id": "input_select.radio_type",
                        "option": call.data["type"],
                    },
                )

            elif media_source == ais_global.G_AN_PODCAST:
                self.hass.services.call(
                    "input_select",
                    "select_option",
                    {
                        "entity_id": "input_select.podcast_type",
                        "option": call.data["type"],
                    },
                )

                self.hass.services.call(
                    "ais_cloud",
                    "get_podcast_tracks",
                    {
                        "lookup_url": call.data["lookup_url"],
                        "podcast_name": call.data["name"],
                        "image_url": call.data["image_url"],
                    },
                )
                # switch UI to Podcast
                self.hass.services.call(
                    "ais_ai_service", "switch_ui", {"mode": "Podcast"}
                )

    def play_prev(self, call):
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_RADIO:
            track_list = "sensor.radiolist"
        elif media_source == ais_global.G_AN_PODCAST:
            track_list = "sensor.podcastlist"
        elif media_source == ais_global.G_AN_MUSIC:
            track_list = "sensor.youtubelist"
        elif media_source == ais_global.G_AN_SPOTIFY_SEARCH:
            track_list = "sensor.spotifysearchlist"
        elif media_source == ais_global.G_AN_SPOTIFY:
            track_list = "sensor.spotifylist"
        elif media_source == ais_global.G_AN_BOOKMARK:
            track_list = "sensor.aisbookmarkslist"
        elif media_source == ais_global.G_AN_FAVORITE:
            track_list = "sensor.aisfavoriteslist"
        elif media_source == ais_global.G_AN_AUDIOBOOK:
            media_source = ais_global.G_AN_AUDIOBOOK_CHAPTER
            track_list = "sensor.audiobookschapterslist"
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
        if (
            ais_ai.CURR_ENTITIE == "media_player.wbudowany_glosnik"
            and ais_ai.CURR_BUTTON_CODE in (21, 22)
        ):
            self.hass.services.call(
                "ais_ai_service", "say_it", {"text": track["title"]}
            )
        # play
        self.hass.services.call(
            "ais_cloud", "play_audio", {"media_source": media_source, "id": prev_id}
        )

    def play_next(self, call):
        media_source = call.data["media_source"]
        if media_source == ais_global.G_AN_RADIO:
            track_list = "sensor.radiolist"
        elif media_source == ais_global.G_AN_PODCAST:
            track_list = "sensor.podcastlist"
        elif media_source == ais_global.G_AN_MUSIC:
            track_list = "sensor.youtubelist"
        elif media_source == ais_global.G_AN_SPOTIFY_SEARCH:
            track_list = "sensor.spotifysearchlist"
        elif media_source == ais_global.G_AN_SPOTIFY:
            track_list = "sensor.spotifylist"
        elif media_source == ais_global.G_AN_BOOKMARK:
            track_list = "sensor.aisbookmarkslist"
        elif media_source == ais_global.G_AN_FAVORITE:
            track_list = "sensor.aisfavoriteslist"
        elif media_source == ais_global.G_AN_AUDIOBOOK:
            media_source = ais_global.G_AN_AUDIOBOOK_CHAPTER
            track_list = "sensor.audiobookschapterslist"
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

        if (
            ais_ai.CURR_ENTITIE == "media_player.wbudowany_glosnik"
            and ais_ai.CURR_BUTTON_CODE in (21, 22)
        ):
            self.hass.services.call(
                "ais_ai_service", "say_it", {"text": track["title"]}
            )
        # play
        self.hass.services.call(
            "ais_cloud", "play_audio", {"media_source": media_source, "id": next_id}
        )

    # youtube or spotify
    def change_audio_service(self, call):
        # we have only 2 now we can toggle
        self.hass.services.call(
            "input_select",
            "select_next",
            {"entity_id": "input_select.ais_music_service"},
        )

    # send audio from AIS to play on selected speaker
    def send_audio_to_speaker(self, call):
        if "media_player" not in call.data:
            return
        media_player = call.data["media_player"]
        state = self.hass.states.get(ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID)
        attr = state.attributes
        media_content_id = attr.get("media_content_id")
        if media_content_id is not None:
            self.hass.services.call(
                "media_player",
                "play_media",
                {
                    "entity_id": media_player,
                    "media_content_type": "music",
                    "media_content_id": media_content_id,
                },
            )

    def get_players(self, call, hass):
        global G_PLAYERS
        G_PLAYERS = []
        players_lv = []
        if "device_name" in call.data:
            unique_id = None
            if "ais_gate_client_id" in call.data:
                unique_id = call.data.get("ais_gate_client_id")
            elif "MacWlan0" in call.data:
                unique_id = call.data.get("MacWlan0")
            elif "MacEth0" in call.data:
                unique_id = call.data.get("MacEth0")
            if unique_id is None:
                return
            # check if this device already exists
            entity_id = slugify(call.data.get("device_name") + "_" + unique_id)
            m_player = hass.states.get("media_player." + entity_id)
            do_disco = False
            if m_player is None:
                do_disco = True
            else:
                if m_player.state == STATE_UNAVAILABLE:
                    do_disco = True
            if do_disco:
                hass.async_run_job(
                    async_load_platform(
                        hass,
                        "media_player",
                        "ais_exo_player",
                        {
                            CONF_NAME: call.data.get("device_name") + "_" + unique_id,
                            CONF_IP_ADDRESS: call.data.get(CONF_IP_ADDRESS),
                            "unique_id": unique_id,
                        },
                        hass.config,
                    )
                )
            else:
                # update player info
                self.hass.services.call(
                    "ais_exo_player",
                    "update_attributes",
                    {
                        "entity_id": entity_id,
                        CONF_IP_ADDRESS: call.data.get(CONF_IP_ADDRESS),
                    },
                )
        # take the info about normal players
        entities = hass.states.async_all()
        for entity in entities:
            if entity.entity_id.startswith("media_player."):
                player = {}
                friendly_name = entity.attributes.get("friendly_name")
                device_ip = entity.attributes.get("device_ip")
                player["friendly_name"] = friendly_name
                player["entity_id"] = entity.entity_id
                player["device_ip"] = device_ip
                G_PLAYERS.append(player)
                players_lv.append(friendly_name)
                # add player to group if it's not added
                hass.async_add_job(
                    hass.services.async_call(
                        "group",
                        "set",
                        {
                            "object_id": "audio_player",
                            "add_entities": [entity.entity_id],
                        },
                    )
                )
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
            "input_select",
            "set_options",
            {"entity_id": "input_select.rss_news_category", "options": types},
        )

    def get_rss_news_channels(self, call):
        """Load news channels of the for the selected category."""
        if "rss_news_category" not in call.data:
            return []
        if call.data["rss_news_category"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                "input_select",
                "set_options",
                {
                    "entity_id": "input_select.rss_news_channel",
                    "options": [ais_global.G_EMPTY_OPTION],
                },
            )
            return
        ws_resp = self.cloud.audio_name(
            ais_global.G_AN_NEWS, call.data["rss_news_category"]
        )
        json_ws_resp = ws_resp.json()
        names = [ais_global.G_EMPTY_OPTION]
        self.news_channels = []
        for item in json_ws_resp["data"]:
            names.append(item["NAME"])
            self.news_channels.append(item)
        self.hass.services.call(
            "input_select",
            "set_options",
            {"entity_id": "input_select.rss_news_channel", "options": names},
        )
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai

        if (
            ais_ai.CURR_ENTITIE == "input_select.rss_news_category"
            and ais_ai.CURR_BUTTON_CODE == 23
        ):
            ais_ai.set_curr_entity(self.hass, "input_select.rss_news_channel")
            self.hass.services.call(
                "ais_ai_service", "say_it", {"text": "Wybierz kanał wiadomości"}
            )

    def get_rss_news_items(self, call):
        import feedparser
        import io

        if "rss_news_channel" not in call.data:
            return
        if call.data["rss_news_channel"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                "input_select",
                "set_options",
                {
                    "entity_id": "input_select.rss_news_item",
                    "options": [ais_global.G_EMPTY_OPTION],
                },
            )
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
            self.hass.services.call("ais_ai_service", "say_it", {"text": "pobieram"})
            try:
                try:
                    resp = requests.get(check_url(_lookup_url), timeout=3.0)
                except requests.ReadTimeout:
                    _LOGGER.warning("Timeout when reading RSS %s", _lookup_url)
                    self.hass.services.call(
                        "ais_ai_service",
                        "say_it",
                        {
                            "text": "Nie można wiadomości . Brak odpowiedzi z "
                            + rss_news_channel
                        },
                    )
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
                    list_info[list_idx]["type"] = ""
                    list_info[list_idx]["icon"] = "mdi:voice"
                    list_idx = list_idx + 1

                # update list
                self.hass.states.async_set("sensor.rssnewslist", -1, list_info)

                if len(d.entries) == 0:
                    self.hass.services.call(
                        "ais_ai_service",
                        "say_it",
                        {"text": "brak artykułów, wybierz inny kanał"},
                    )
                    return

                if selected_by_voice_command:
                    self.hass.services.call(
                        "ais_ai_service",
                        "say_it",
                        {
                            "text": "mamy "
                            + str(len(d.entries))
                            + " wiadomości z "
                            + rss_news_channel
                            + ", czytam najnowszy artykuł: "
                            + list_info[0]["title"]
                        },
                    )

                    self.hass.states.async_set("sensor.rssnewslist", 0, list_info)
                    # call to read
                    # select_rss_news_item
                    # TODO
                else:
                    self.hass.services.call(
                        "ais_ai_service",
                        "say_it",
                        {
                            "text": "mamy "
                            + str(len(d.entries))
                            + " wiadomości, wybierz artykuł"
                        },
                    )
                    # check if the change was done form remote
                    import homeassistant.components.ais_ai_service as ais_ai

                    if (
                        ais_ai.CURR_ENTITIE == "input_select.rss_news_channel"
                        and ais_ai.CURR_BUTTON_CODE == 23
                    ):
                        ais_ai.set_curr_entity(self.hass, "sensor.rssnewslist")

            except Exception as e:
                self.hass.services.call(
                    "ais_ai_service",
                    "say_it",
                    {"text": "Nie można pobrać wiadomości z: " + rss_news_channel},
                )

    def select_rss_news_item(self, call):
        """Get text for the selected item."""
        if "id" not in call.data:
            return
        news_text = ""
        # find the url and read the text
        rss_news_item_id = int(call.data["id"])
        state = self.hass.states.get("sensor.rssnewslist")
        attr = state.attributes
        track = attr.get(rss_news_item_id)
        # update list
        self.hass.states.async_set("sensor.rssnewslist", rss_news_item_id, attr)

        if track["description"] is not None:
            news_text = track["description"]

        if track["uri"] is not None:
            try:
                import requests
                from readability import Document

                response = requests.get(check_url(track["uri"]), timeout=5)
                response.encoding = "utf-8"
                doc = Document(response.text)
                doc_s = doc.summary()
                if len(doc_s) > 0:
                    news_text = doc_s
            except Exception as e:
                _LOGGER.error("Can not get article " + str(e))
        from bs4 import BeautifulSoup

        clear_text = BeautifulSoup(news_text, "lxml").text
        self.hass.services.call("ais_ai_service", "say_it", {"text": clear_text})
        news_text = news_text.replace("<html>", "")
        news_text = news_text.replace("</html>", "")
        news_text = news_text.replace("<body>", "")
        news_text = news_text.replace("</body>", "")
        self.hass.states.async_set(
            "sensor.rssnewstext", news_text[:200], {"text": "" + news_text}
        )

    def select_rss_help_item(self, call):
        """Get text for the selected item."""
        rss_help_text = ""
        if "rss_help_topic" not in call.data:
            return
        if call.data["rss_help_topic"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.states.async_set(
                "sensor.aisrsshelptext",
                "-",
                {"text": "", "friendly_name": "Tekst strony"},
            )
            return
        # we need to build the url and get the text to read
        rss_help_topic = call.data["rss_help_topic"]
        _url = check_url(
            "https://raw.githubusercontent.com/wiki/sviete/AIS-WWW/"
            + rss_help_topic.replace(" ", "-")
            + ".md"
        )
        import requests
        from readability.readability import Document

        response = requests.get(_url, timeout=5)
        doc = Document(response.text)
        rss_help_text += doc.summary()

        from markdown import markdown

        rss_help_text = markdown(rss_help_text)
        import re

        rss_help_text = re.sub(r"<code>(.*?)</code>", " ", rss_help_text)
        rss_help_text = re.sub("#", "", rss_help_text)

        from bs4 import BeautifulSoup

        rss_help_text = BeautifulSoup(rss_help_text, "lxml").text

        self.hass.states.async_set(
            "sensor.aisrsshelptext",
            rss_help_text[:200],
            {"text": "" + response.text, "friendly_name": "Tekst strony"},
        )
        # say only if from remote
        import homeassistant.components.ais_ai_service as ais_ai

        #  binary_sensor.selected_entity / binary_sensor.ais_remote_button
        if (
            ais_ai.CURR_ENTITIE == "input_select.ais_rss_help_topic"
            and ais_ai.CURR_BUTTON_CODE == 23
        ):
            self.hass.services.call(
                "ais_ai_service",
                "say_it",
                {"text": "Czytam stronę pomocy. " + rss_help_text},
            )

    def get_backup_info(
        self,
        call,
        step=0,
        backup_error=None,
        backup_info=None,
        restore_error=None,
        restore_info=None,
    ):
        ws_resp = self.cloud.get_backup_info()
        json_ws_resp = ws_resp.json()
        if backup_error is not None:
            json_ws_resp["backup_error"] = backup_error
        if backup_info is not None:
            json_ws_resp["backup_info"] = backup_info
        if restore_error is not None:
            json_ws_resp["restore_error"] = restore_error
        if restore_info is not None:
            json_ws_resp["restore_info"] = restore_info
        self.hass.states.async_set("sensor.aisbackupinfo", step, json_ws_resp)
        info_text = ""
        if backup_error is not None:
            info_text = info_text + backup_error
        if backup_info is not None:
            info_text = info_text + backup_info
        if restore_error is not None:
            info_text = info_text + restore_error
        if restore_info is not None:
            info_text = info_text + restore_info
        if info_text != "":
            self.hass.services.call("ais_ai_service", "say_it", {"text": info_text})

    def set_backup_step(self, call):
        step = call.data["step"]
        backup_error = ""
        backup_info = ""
        restore_error = ""
        restore_info = ""
        if "backup_error" in call.data:
            backup_error = call.data["backup_error"]
        if "backup_info" in call.data:
            backup_info = call.data["backup_info"]
        if "restore_error" in call.data:
            restore_error = call.data["restore_error"]
        if "restore_info" in call.data:
            restore_info = call.data["restore_info"]
        self.get_backup_info(
            call, step, backup_error, backup_info, restore_error, restore_info
        )

    def do_backup(self, call):
        import subprocess

        password = ""
        # all, ha, zigbee
        backup_type = "all"
        info_text = "kompresuje"
        home_dir = "/data/data/pl.sviete.dom/files/home/"
        if "type" in call.data:
            backup_type = call.data["type"]
        if "password" in call.data:
            password = call.data["password"]
        if password != "":
            info_text += " i szyfruje"
            password = "-p" + password

        # HA backup
        if backup_type in ("all", "ha"):
            # 0. chmod
            try:
                ret = subprocess.check_output(
                    'su -c "chmod -R 755 /data/data/pl.sviete.dom/files/home/AIS"',
                    shell=True,  # nosec
                )
            except Exception as e:
                _LOGGER.error("do_backup chmod: " + str(e))

            # 1. zip files
            self.get_backup_info(
                call,
                1,
                None,
                info_text + " bieżącą konfigurację Home Assistant",
                None,
                None,
            )
            try:
                ret = subprocess.check_output(
                    "rm " + home_dir + "backup.zip", shell=True  # nosec
                )
            except Exception as e:
                pass
            try:
                ret = subprocess.check_output(
                    "7za a -mmt=2 "
                    + password
                    + r" -xr\!deps"
                    + r" -xr\!ais_update"
                    + r" -xr\!*.log"
                    + r" -xr\!*.db"
                    + r" -xr\!home-assistant* "
                    + home_dir
                    + "backup.zip "
                    + home_dir
                    + "AIS/.",
                    shell=True,  # nosec
                )
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                _LOGGER.error("do_backup 7za: " + str(e))
                return
            # 2. check backup size
            # size in bytes 1 Byte = 0.000001 MB
            b = os.path.getsize(home_dir + "backup.zip")
            mb = b * 0.000001
            if mb > 11:
                self.get_backup_info(
                    call,
                    0,
                    "Maksymalny rozmiar kopii zapasowej konfiguracji Home Assistant to 10 MB. "
                    + "Twoja konfiguracja zajmuje "
                    + str(round(mb))
                    + " MB. Przed wykonaniem kopii usuń niepotrzebne zasoby z galerii (np. pliki wideo)."
                    + " Jeżeli dodałeś ręcznie jakieś niestandardowe komponenty do folderu z konfiguracją: "
                    + "~/AIS to też zajmują one miejsce i zalecamy je usunąć przed wykonaniem kopii.",
                )
                _LOGGER.error("Backup size, is to big, in bytes: " + str(b))
                return

            # 3. upload to cloud
            self.get_backup_info(
                call,
                1,
                None,
                "Wysyłam kopie konfiguracji Home Assistant do portalu integratora",
                None,
                None,
            )
            try:
                ws_resp = self.cloud.post_backup(home_dir + "backup.zip", "ha")
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                _LOGGER.error("post_backup ha: " + str(e))
                return

            if ws_resp.status_code != 200:
                self.get_backup_info(
                    call,
                    0,
                    "Podczas wysyłania kopii konfiguracji Home Assistant wystąpił problem "
                    + ws_resp.text,
                )
                return

            # clean up
            try:
                ret = subprocess.check_output(
                    "rm " + home_dir + "backup.zip", shell=True  # nosec
                )
            except Exception as e:
                pass

        # Zigbee backup
        if backup_type in ("all", "zigbee"):
            # 1. zip files
            self.get_backup_info(
                call, 1, None, info_text + " bieżącą konfigurację Zigbee", None, None
            )
            # clean up
            try:
                ret = subprocess.check_output(
                    "rm " + home_dir + "zigbee_backup.zip", shell=True  # nosec
                )
            except Exception as e:
                pass
            try:
                c = (
                    "7za a -mmt=2 "
                    + password
                    + r" -xr\!log "
                    + home_dir
                    + "zigbee_backup.zip "
                    + home_dir
                    + "zigbee2mqtt/data/."
                )
                _LOGGER.debug("c: " + c)
                ret = subprocess.check_output(
                    "7za a -mmt=2 "
                    + password
                    + r" -xr\!logs "
                    + home_dir
                    + "zigbee_backup.zip "
                    + home_dir
                    + "zigbee2mqtt/data/.",
                    shell=True,  # nosec
                )
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                _LOGGER.error("do_backup zigbee 7za: " + str(e))
                return
            # 2. check backup size
            # size in bytes 1 Byte = 0.000001 MB
            b = os.path.getsize(home_dir + "zigbee_backup.zip")
            mb = b * 0.000001
            if mb > 11:
                self.get_backup_info(
                    call,
                    0,
                    "Maksymalny rozmiar kopii zapasowej konfiguracji Zigbee to 10 MB. "
                    + "Twoja konfiguracja zajmuje "
                    + str(round(mb)),
                )
                _LOGGER.error("Backup zigbee size, is to big, in bytes: " + str(b))
                return

            # 3. upload to cloud
            self.get_backup_info(
                call,
                1,
                None,
                "Wysyłam kopie konfiguracji zigbee do portalu integratora",
                None,
                None,
            )
            try:
                ws_resp = self.cloud.post_backup(
                    home_dir + "zigbee_backup.zip", "zigbee"
                )
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                _LOGGER.error("post_backup zigbee: " + str(e))
                return

            if ws_resp.status_code != 200:
                self.get_backup_info(
                    call,
                    0,
                    "Podczas wysyłania kopii konfiguracji zigbee wystąpił problem "
                    + ws_resp.text,
                )
                return
            # clean up
            try:
                ret = subprocess.check_output(
                    "rm " + home_dir + "zigbee_backup.zip", shell=True  # nosec
                )
            except Exception as e:
                pass
        # refresh
        self.get_backup_info(call, 0, "", "Kopia zapasowa konfiguracji wykonana")

    def restore_backup(self, call):
        import subprocess

        home_dir = "/data/data/pl.sviete.dom/files/home/"
        password = ""
        info_text = ""
        # all, ha, zigbee
        backup_type = ""
        if "password" in call.data:
            password = call.data["password"]
        if password != "":
            info_text = " i deszyfruje"
        if "type" in call.data:
            backup_type = call.data["type"]

        # HA backup
        if backup_type in ("all", "ha"):
            # we need to use password even if it's empty - to prevent the prompt
            password = "-p" + password
            # 1. download
            self.get_backup_info(
                call, 1, None, None, None, "Pobieram kopie konfiguracji"
            )
            try:
                ws_resp = self.cloud.download_backup(home_dir + "backup.zip", "ha")
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                return
            # 2. extract
            self.get_backup_info(call, 1, None, None, None, "Rozpakowuje" + info_text)
            try:
                ret = subprocess.check_output(
                    "7z x -mmt=2 "
                    + password
                    + " -o"
                    + home_dir
                    + "AIS_BACKUP "
                    + home_dir
                    + "backup.zip "
                    + "-y",
                    shell=True,  # nosec
                )
            except Exception as e:
                self.get_backup_info(call, 0, None, None, str(e), None)
                return
            # 3. copy files to AIS
            self.get_backup_info(call, 1, None, None, None, "Podmieniam konfigurację ")
            try:
                ret = subprocess.check_output(
                    "cp -fa " + home_dir + "AIS_BACKUP/. " + home_dir + "AIS",
                    shell=True,  # nosec
                )
                ret = subprocess.check_output(
                    "rm " + home_dir + "backup.zip", shell=True  # nosec
                )
                ret = subprocess.check_output(
                    "rm -rf " + home_dir + "AIS_BACKUP", shell=True  # nosec
                )

            except Exception as e:
                self.get_backup_info(call, 0, None, None, str(e), None)
                return

        # Zigbee backup
        if backup_type in ("all", "zigbee"):
            # we need to use password even if it's empty - to prevent the prompt
            if password == "":
                password = "-p" + password
            # 1. download
            self.get_backup_info(
                call, 1, None, None, None, "Pobieram kopie konfiguracji zigbee"
            )
            try:
                ws_resp = self.cloud.download_backup(
                    home_dir + "zigbee_backup.zip", "zigbee"
                )
            except Exception as e:
                self.get_backup_info(call, 0, str(e))
                return
            # 2. extract
            self.get_backup_info(call, 1, None, None, None, "Rozpakowuje" + info_text)
            try:
                ret = subprocess.check_output(
                    "7z x -mmt=2 "
                    + password
                    + " -o"
                    + home_dir
                    + "AIS_ZIGBEE_BACKUP "
                    + home_dir
                    + "zigbee_backup.zip "
                    + "-y",
                    shell=True,  # nosec
                )
            except Exception as e:
                self.get_backup_info(call, 0, None, None, str(e), None)
                return
            # 3. copy files to AIS
            self.get_backup_info(
                call, 1, None, None, None, "Podmieniam konfigurację zigbee "
            )
            try:
                ret = subprocess.check_output(
                    "cp -fa "
                    + home_dir
                    + "AIS_ZIGBEE_BACKUP/. "
                    + home_dir
                    + "zigbee2mqtt/data",
                    shell=True,  # nosec
                )
                ret = subprocess.check_output(
                    "rm " + home_dir + "zigbee_backup.zip", shell=True  # nosec
                )
                ret = subprocess.check_output(
                    "rm -rf " + home_dir + "AIS_ZIGBEE_BACKUP", shell=True  # nosec
                )

            except Exception as e:
                self.get_backup_info(call, 0, None, None, str(e), None)
                return

        # refresh
        self.get_backup_info(
            call, 0, None, None, None, "OK, przywrócono konfigurację z  kopii"
        )

    def enable_gate_pairing_by_pin(self, call):
        ws_resp = self.cloud.get_gate_parring_pin()
        json_ws_resp = ws_resp.json()
        pin = json_ws_resp["pin"]
        # set gate_parring_pin
        self.hass.states.set("sensor.gate_pairing_pin", pin)
        # run timer
        self.hass.services.call(
            "timer", "start", {"entity_id": "timer.ais_dom_pin_join", "duration": "120"}
        )
        # voice info
        self.hass.services.call(
            "ais_ai_service",
            "say_it",
            {"text": "Parowanie z bramką za pomocą PIN włączone"},
        )
