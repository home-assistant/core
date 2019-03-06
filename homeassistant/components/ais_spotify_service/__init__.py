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

from homeassistant.ais_dom.ais_global import G_AIS_SECURE_ANDROID_ID_DOM
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()
REQUIREMENTS = ['spotipy-homeassistant==2.4.4.dev1']

DOMAIN = 'ais_spotify_service'
PERSISTENCE_GM_SONGS = '/.dom/gm_songs.json'
_LOGGER = logging.getLogger(__name__)
SPOTIFY_TOKEN = None
SPOTIFY_REFRESH_TOKEN = None


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})
    yield from get_keys_async(hass)
    # TODO
    if SPOTIFY_TOKEN is None:
        return True

    _LOGGER.info("Initialize the authors list.")
    data = hass.data[DOMAIN] = SpotifyData(hass, config)
    yield from data.async_load_all_songs()

    # register services
    def get_album(call):
        _LOGGER.info("get_album")
        data.get_album(call)

    def get_playlist(call):
        _LOGGER.info("get_playlist")
        data.get_playlist(call)

    def select_track(call):
        _LOGGER.info("select_track")
        data.select_track(call)

    hass.services.async_register(
        DOMAIN, 'get_album', get_album)
    hass.services.async_register(
        DOMAIN, 'get_playlist', get_playlist)
    hass.services.async_register(
        DOMAIN, 'select_track', select_track)

    return True


@asyncio.coroutine
def get_keys_async(hass):
    def load_token():
        global SPOTIFY_TOKEN, SPOTIFY_REFRESH_TOKEN
        try:
            ws_resp = aisCloud.key("spotify_token")
            json_ws_resp = ws_resp.json()
            SPOTIFY_TOKEN = json_ws_resp["key"]
            ws_resp = aisCloud.key("spotify_refresh_token")
            json_ws_resp = ws_resp.json()
            SPOTIFY_REFRESH_TOKEN = json_ws_resp["key"]
        except Exception as e:
            _LOGGER.error("No credentials to Spotify: " + str(e))

        """Set up the Spotify platform."""
        import spotipy.oauth2

        callback_url = '{}{}'.format(hass.config.api.base_url, AUTH_CALLBACK_PATH)
        cache = config.get(CONF_CACHE_PATH, hass.config.path(DEFAULT_CACHE_PATH))
        oauth = spotipy.oauth2.SpotifyOAuth(
            config.get(CONF_CLIENT_ID), config.get(CONF_CLIENT_SECRET),
            callback_url, scope=SCOPE,
            cache_path=cache)
        token_info = oauth.get_cached_token()
        if not token_info:
            _LOGGER.info("no token; requesting authorization")
            hass.http.register_view(SpotifyAuthCallbackView(
                config, add_entities, oauth))
            request_configuration(hass, config, add_entities, oauth)
            return
        if hass.data.get(DOMAIN):
            configurator = hass.components.configurator
            configurator.request_done(hass.data.get(DOMAIN))
            del hass.data[DOMAIN]
        player = SpotifyMediaPlayer(
            oauth, config.get(CONF_NAME, DEFAULT_NAME), config[CONF_ALIASES])
        add_entities([player], True)

    yield from hass.async_add_job(load_token)


class SpotifyData:
    """Class to hold audiobooks data."""

    def __init__(self, hass, config):
        """Initialize the books authors."""
        global GM_DEV_KEY
        global G_GM_MOBILE_CLIENT_API
        self.hass = hass
        self.all_gm_tracks = []
        self.selected_books = []
        import spotipy
        self.sp = spotipy.Spotify()


    def get_album(self, call):
        """Load album for the selected author."""
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
        if ("book_chapter" not in call.data):
            _LOGGER.error("No book_chapter")
            return
        if call.data["book_chapter"] == ais_global.G_EMPTY_OPTION:
            # stop all players
            # TODO - stop only the player selected for books
            self.hass.services.call('media_player', 'media_stop', {"entity_id": "all"})
            return
        book_chapter = call.data["book_chapter"]
        _url = None
        _audio_info = {}
        for ch in G_SELECTED_TRACKS:
            if(ch["name"] == book_chapter):
                # TODO audio info is changing type from dict to str!!!
                # that is why it is again declared - check what is going on...
                _url = G_GM_MOBILE_CLIENT_API.get_stream_url(ch["id"])
                _audio_info = {}
                _audio_info["IMAGE_URL"] = ch["image"]
                _audio_info["NAME"] = ch["name"]
                _audio_info["MEDIA_SOURCE"] = ais_global.G_AN_AUDIOBOOK
                _audio_info = json.dumps(_audio_info)

        if _url is not None:
            player_name = self.hass.states.get(
                'input_select.book_player').state
            player = ais_cloud.get_player_data(player_name)
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
