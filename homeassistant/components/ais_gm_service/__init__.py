# -*- coding: utf-8 -*-
"""
Support for AIS knowledge

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
import json
import os.path
from operator import itemgetter

from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()
REQUIREMENTS = ['gmusicapi==12.0.0']

DOMAIN = 'ais_gm_service'
PERSISTENCE_GM_SONGS = '/.dom/gm_songs.json'
_LOGGER = logging.getLogger(__name__)
GM_URL = 'https://kgsearch.googleapis.com/v1/entities:search'
GM_USER = None
GM_PASS = None
GM_DEV_KEY = None
G_SELECTED_TRACKS = []
G_GM_MOBILE_CLIENT_API = None


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})
    yield from get_keys_async(hass)
    # TODO
    if GM_USER is None:
        return True

    _LOGGER.info("Initialize the authors list.")
    data = hass.data[DOMAIN] = GMusicData(hass, config)
    yield from data.async_load_all_songs()

    # register services
    def get_books(call):
        _LOGGER.info("get_books")
        data.get_books(call)

    def get_chapters(call):
        _LOGGER.info("get_chapters")
        data.get_chapters(call)

    def select_chapter(call):
        _LOGGER.info("select_chapter")
        data.select_chapter(call)

    hass.services.async_register(
        DOMAIN, 'get_books', get_books)
    hass.services.async_register(
        DOMAIN, 'get_chapters', get_chapters)
    hass.services.async_register(
        DOMAIN, 'select_chapter', select_chapter)

    return True


@asyncio.coroutine
def get_keys_async(hass):
    def load():
        global GM_DEV_KEY, GM_USER, GM_PASS
        try:
            ws_resp = aisCloud.key("gm_user_key")
            json_ws_resp = ws_resp.json()
            GM_USER = json_ws_resp["key"]
            ws_resp = aisCloud.key("gm_pass_key")
            json_ws_resp = ws_resp.json()
            GM_PASS = json_ws_resp["key"]
            try:
                ws_resp = aisCloud.key("gm_dev_key")
                json_ws_resp = ws_resp.json()
                GM_DEV_KEY = json_ws_resp["key"]
            except:
                GM_DEV_KEY = None
                _LOGGER.warning("No GM device key we will use MAC address of gate.")
        except Exception as e:
            _LOGGER.error("No credentials to Google Music: " + str(e))

    yield from hass.async_add_job(load)


class GMusicData:
    """Class to hold audiobooks data."""

    def __init__(self, hass, config):
        """Initialize the books authors."""
        global GM_DEV_KEY
        global G_GM_MOBILE_CLIENT_API
        self.hass = hass
        self.all_gm_tracks = []
        self.selected_books = []
        _LOGGER.info("GM_USER: " + GM_USER + " GM_PASS: *******" + " GM_DEV_KEY: " + str(GM_DEV_KEY))
        from gmusicapi import Mobileclient
        G_GM_MOBILE_CLIENT_API = Mobileclient()

        # if GM_DEV_KEY is None:
        #     G_GM_MOBILE_CLIENT_API.login(GM_USER, GM_PASS, Mobileclient.FROM_MAC_ADDRESS)
        # else:
        #     G_GM_MOBILE_CLIENT_API.login(GM_USER, GM_PASS, GM_DEV_KEY)
        #
        G_GM_MOBILE_CLIENT_API.oauth_login('3cf7d4cc166ab0ee')
        if not G_GM_MOBILE_CLIENT_API.is_authenticated():
            _LOGGER.error("Failed to log in, check Google Music api")
            return False
        else:
            _LOGGER.info("OK - we are in Google Music")
            registered_devices = G_GM_MOBILE_CLIENT_API.get_registered_devices()
            # for d in registered_devices:
            #     if d['id'].startswith('0x'):
            #         _LOGGER.warning("Your device ID in Google Music: " + str(d['id'][2:]) + " " + str(d))
            #     else:
            #         _LOGGER.warning("Your device ID in Google Music: " + str(d['id'].replace(':', '')) + " " + str(d))
            #
            # # trying to find first android device
            # if GM_DEV_KEY is None:
            #     for device in registered_devices:
            #         if device['type'] == 'ANDROID':
            #             GM_DEV_KEY = device['id'][2:]
            #             break
            # # try to find gate id in devices or take the last one
            # if GM_DEV_KEY is None:
            #     for device in registered_devices:
            #         if device['id'].startswith('0x'):
            #             d = device['id'][2:]
            #         else:
            #             d = device['id'].replace(':', '')
            #
            #         GM_DEV_KEY = d
            #         if d == get_sercure_android_id_dom.replace('dom-', ''):
            #             break
            # # try to register the gate id - Providing an unregistered mobile device id will register it to your account
            # if GM_DEV_KEY is None:
            #     GM_DEV_KEY = get_sercure_android_id_dom.replace('dom-', '')
            #G_GM_MOBILE_CLIENT_API.logout()
            #G_GM_MOBILE_CLIENT_API = None
            #G_GM_MOBILE_CLIENT_API = Mobileclient()
            #G_GM_MOBILE_CLIENT_API.login(GM_USER, GM_PASS, GM_DEV_KEY)
            #_LOGGER.info("GM_USER: " + GM_USER + " GM_PASS: *******" + " GM_DEV_KEY: " + str(GM_DEV_KEY))

    def get_books(self, call):
        """Load books for the selected author."""
        if ("author" not in call.data):
            _LOGGER.error("No author")
            return []
        if call.data["author"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.book_name",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return
        books = [ais_global.G_EMPTY_OPTION]
        self.selected_books = []
        for chapters in self.all_gm_tracks:
            if(chapters["artist"] == call.data["author"]):
                self.selected_books.append(chapters)
                if(chapters["book"] not in books):
                    books.append(chapters["book"])
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.book_name",
                "options": sorted(books)})
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'input_select.book_autor':
            ais_ai.set_curr_entity(
                self.hass,
                'input_select.book_name')
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Wybierz książkę"
                })

    def get_chapters(self, call):
        """Load chapters for the selected book."""
        global G_SELECTED_TRACKS
        if ("book" not in call.data):
            _LOGGER.error("No book")
            return []
        if call.data["book"] == ais_global.G_EMPTY_OPTION:
            # reset status for item below
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.book_chapter",
                    "options": [ais_global.G_EMPTY_OPTION]})
            return
        G_SELECTED_TRACKS = []
        tracks = []
        for ch in self.selected_books:
            if(ch["book"] == call.data["book"]):
                G_SELECTED_TRACKS.append(ch)
                tracks.append(
                        {"no": int(ch["track_no"]), "name": ch["name"]})

        t = [ais_global.G_EMPTY_OPTION]
        tracks = sorted(tracks, key=itemgetter('no'))
        for st in tracks:
            t.append(st["name"])
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.book_chapter",
                "options": t})
        # check if the change was done form remote
        import homeassistant.components.ais_ai_service as ais_ai
        if ais_ai.CURR_ENTITIE == 'input_select.book_name':
            ais_ai.set_curr_entity(
                self.hass,
                'input_select.book_chapter')
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Wybierz rozdział"
                })

    def select_chapter(self, call):
        """Get chapter stream url for the selected name."""
        if "book_chapter" not in call.data:
            _LOGGER.error("No book_chapter")
            return
        if call.data["book_chapter"] == ais_global.G_EMPTY_OPTION:
            # stop all players
            self.hass.services.call('media_player', 'media_stop', {"entity_id": "all"})
            return
        book_chapter = call.data["book_chapter"]
        _url = None
        _audio_info = {}
        for ch in G_SELECTED_TRACKS:
            if ch["name"] == book_chapter:
                _url = G_GM_MOBILE_CLIENT_API.get_stream_url(ch["id"])
                _audio_info = {"IMAGE_URL": ch["image"], "NAME": ch["name"],
                               "MEDIA_SOURCE": ais_global.G_AN_AUDIOBOOK, "media_content_id": _url}
                _audio_info = json.dumps(_audio_info)
                break
        if _url is not None:
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info
                })


    @asyncio.coroutine
    def async_load_all_songs(self):
        """Load all the songs and cache the JSON."""

        def load():
            """Load the items synchronously."""
            items = []
            path = self.hass.config.path() + PERSISTENCE_GM_SONGS
            if not os.path.isfile(path):
                items = G_GM_MOBILE_CLIENT_API.get_all_songs()
                with open(path, 'w+') as myfile:
                    myfile.write(json.dumps(items))
            else:
                with open(path) as file:
                    items = json.loads(file.read())

            for track in items:
                t = {}
                track_id = track.get('id', track.get('nid'))
                if track_id is not None:
                    t["id"] = track_id
                    t["name"] = track.get('title')
                    t["artist"] = track.get('artist', '')
                    t["book"] = track.get('album', '')
                    t["track_no"] = track.get('trackNumber', 1)
                    t["length"] = track.get('durationMillis')
                    t["image"] = track.get('albumArtRef')
                    if (t["image"]):
                        try:
                            t["image"] = t["image"][0]['url']
                        except Exception as e:
                            _LOGGER.info("albumArtRef: " + t["image"])

                self.all_gm_tracks.append(t)
            authors = [ais_global.G_EMPTY_OPTION]
            for chapters in self.all_gm_tracks:
                if(chapters["artist"] not in authors):
                    if (len(chapters["artist"]) > 0):
                        authors.append(chapters["artist"])
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.book_autor",
                    "options": sorted(authors)})

        yield from self.hass.async_add_job(load)
