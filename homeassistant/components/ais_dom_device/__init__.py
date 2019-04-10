"""
Support for interacting with Spotify.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.spotify/
"""
import logging
import asyncio
from homeassistant.ais_dom import ais_global
from homeassistant.components import ais_cloud
from .config_flow import configured_service
from homeassistant.util.async_ import run_coroutine_threadsafe

aisCloud = ais_cloud.AisCloudWS()

REQUIREMENTS = ['spotipy-homeassistant==2.4.4.dev1']

_LOGGER = logging.getLogger(__name__)

AUTH_CALLBACK_NAME = 'api:ais_spotify_service'
AUTH_CALLBACK_PATH = ''

CONF_ALIASES = 'aliases'
CONF_CACHE_PATH = 'cache_path'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
AIS_SPOTIFY_TOKEN = None
OAUTH_CLIENT_ID = None

CONFIGURATOR_DESCRIPTION = 'Aby połączyć swoje konto Spotify, kliknij link:'
CONFIGURATOR_LINK_NAME = 'Połącz konto Spotify'
CONFIGURATOR_SUBMIT_CAPTION = 'OK, dostęp dodany!'

DEFAULT_CACHE_PATH = '.dom/.ais-dom-spotify-token-cache'
DEFAULT_NAME = 'Spotify'
DEPENDENCIES = ['http']
DOMAIN = 'ais_dom_device'

ICON = 'mdi:spotify'

SCOPE = 'app-remote-control streaming user-read-email'
G_SPOTIFY_FOUND = []
_CONFIGURING = {}


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Spotify platform."""
    import spotipy.oauth2
    import json
    global AIS_SPOTIFY_TOKEN

    try:
        ws_resp = aisCloud.key("spotify_oauth")
        json_ws_resp = ws_resp.json()
        spotify_redirect_url = json_ws_resp["SPOTIFY_REDIRECT_URL"]
        spotify_client_id = json_ws_resp["SPOTIFY_CLIENT_ID"]
        spotify_client_secret = json_ws_resp["SPOTIFY_CLIENT_SECRET"]
        spotify_scope = json_ws_resp["SPOTIFY_SCOPE"]
        try:
            ws_resp = aisCloud.key("spotify_token")
            key = ws_resp.json()["key"]
            AIS_SPOTIFY_TOKEN = json.loads(key)
        except:
            AIS_SPOTIFY_TOKEN = None
            _LOGGER.info("No AIS_SPOTIFY_TOKEN")
    except Exception as e:
        _LOGGER.error("No spotify oauth info: " + str(e))
        return True

    cache = hass.config.path(DEFAULT_CACHE_PATH)
    _LOGGER.info("take gate_id")
    gate_id = ais_global.get_sercure_android_id_dom()
    _LOGGER.info("gate_id: " + str(gate_id))
    oauth = spotipy.oauth2.SpotifyOAuth(spotify_client_id, spotify_client_secret, spotify_redirect_url,
                                        scope=spotify_scope, cache_path=cache, state=gate_id)
    setUrl(oauth.get_authorize_url())
    token_info = oauth.get_cached_token()
    if not token_info:
        _LOGGER.info("no spotify token in cache;")
        if AIS_SPOTIFY_TOKEN is not None:
            with open(cache, 'w') as outfile:
                json.dump(AIS_SPOTIFY_TOKEN, outfile)
            token_info = oauth.get_cached_token()
        if not token_info:
            _LOGGER.info("no spotify token exit")
            return True

    # register services
    data = hass.data[DOMAIN] = SpotifyData(hass, oauth)


    @asyncio.coroutine
    def search(call):
        _LOGGER.info("search " + str(call))
        yield from data.process_search_async(call)

    def select_track_name(call):
        _LOGGER.info("select_track_name")
        data.process_select_track_name(call)

    def select_track_uri(call):
        _LOGGER.info("select_track_uri")
        data.select_track_uri(call)

    def change_play_queue(call):
        _LOGGER.info("change_play_queue")
        data.change_play_queue(call)

    hass.services.async_register(DOMAIN, 'search', search)
    hass.services.async_register(DOMAIN, 'select_track_name', select_track_name)
    hass.services.async_register(DOMAIN, 'select_track_uri', select_track_uri)
    hass.services.async_register(DOMAIN, 'change_play_queue', change_play_queue)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up spotify token as config entry."""
    # setup the Spotify
    if AIS_SPOTIFY_TOKEN is None:
        await async_setup(hass, hass.config)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.info("Remove the Spotify token from AIS gate and cloud")
    try:
        import os
        os.remove(hass.config.path(DEFAULT_CACHE_PATH))
        _LOGGER.info("Token from cache file removed")
    except Exception as e:
        _LOGGER.error("Error removing token cache file " + str(e))
    try:
        ws_resp = aisCloud.delete_key("spotify_token")
        key = ws_resp.json()["key"]
        _LOGGER.info("Token from AIS cloud removed " + str(key))
    except Exception as e:
        _LOGGER.error("Error removing token from cloud " + str(e))

    # setup the Spotify
    await async_setup(hass, hass.config)
    return True


class SpotifyData:
    """Representation of a Spotify browser."""

    def __init__(self, hass, oauth):
        """Initialize."""
        self.hass = hass
        self._oauth = oauth
        self._spotify = None
        self._user = None
        self._token_info = self._oauth.get_cached_token()

    def refresh_spotify_instance(self):
        """Fetch a new spotify instance."""
        import spotipy

        token_refreshed = False
        need_token = (self._token_info is None or
                      self._oauth.is_token_expired(self._token_info))
        if need_token:
            new_token = \
                self._oauth.refresh_access_token(
                    self._token_info['refresh_token'])
            # skip when refresh failed
            if new_token is None:
                return

            self._token_info = new_token
            token_refreshed = True
        if token_refreshed or self._spotify is None:
            self._spotify = spotipy.Spotify(auth=self._token_info.get('access_token'))
            self._user = self._spotify.me()

    def get_list_from_results(self, results, type):
        global G_SPOTIFY_FOUND
        items = []
        title_prefix = ''
        titles = []
        prev_name = ""
        item_owner_id = ''
        if type == 'album':
            items = results['albums']['items']
            title_prefix = 'Album: '
        elif type == 'artist':
            items = results['artists']['items']
            title_prefix = 'Wykonawca: '
        elif type == 'playlist':
            items = results['playlists']['items']
            title_prefix = 'Playlista: '

        for item in items:
            if prev_name == item['name']:
                name = item['name'] + " 2"
            else:
                name = item['name']
            prev_name = name
            if type == 'playlist':
                item_owner_id = item['owner']['id']
            i = {"uri": item['uri'], "title": title_prefix + name, "name": name,
                 "type": type, "item_owner_id": item_owner_id}
            if len(item['images']) > 0:
                i["thumbnail"] = item['images'][0]['url']
            else:
                i["thumbnail"] = "/static/icons/favicon-100x100.png"
            titles.append(title_prefix + name)
            G_SPOTIFY_FOUND.append(i)
        return titles

    @asyncio.coroutine
    def get_tracks_list_async(self, item_uri, item_type, item_owner_id, item_image_url):
        global G_SPOTIFY_TRACKS_INFO
        items_info = {}
        idx = 0
        if item_type == 'album':
            response = self._spotify.album_tracks(item_uri)
            for track in response['items']:
                items_info[idx] = {}
                items_info[idx]["title"] = track["name"]
                items_info[idx]["name"] = track["name"]
                if item_image_url is not None:
                    items_info[idx]["thumbnail"] = item_image_url
                else:
                    items_info[idx]["thumbnail"] = "/static/icons/favicon-100x100.png"
                items_info[idx]["uri"] = track["uri"]
                items_info[idx]["mediasource"] = ais_global.G_AN_SPOTIFY
                items_info[idx]["type"] = track["type"]
                items_info[idx]["icon"] = 'mdi:play'
                idx = idx + 1
        elif item_type == 'artist':
            response = self._spotify.artist_top_tracks(item_uri)
            for track in response['tracks']:
                items_info[idx] = {}
                items_info[idx]["title"] = track["name"]
                items_info[idx]["name"] = track["name"]
                if len(track["album"]["images"]) > 0:
                    items_info[idx]["thumbnail"] = track["album"]["images"][0]["url"]
                else:
                    items_info[idx]["thumbnail"] = "/static/icons/favicon-100x100.png"
                items_info[idx]["uri"] = track["uri"]
                items_info[idx]["mediasource"] = ais_global.G_AN_SPOTIFY
                items_info[idx]["type"] = track["type"]
                items_info[idx]["icon"] = 'mdi:play'
                idx = idx + 1
        else:
            response = self._spotify.user_playlist(item_owner_id, item_uri)
            for items in response['tracks']['items']:
                items_info[idx] = {}
                items_info[idx]["title"] = items["track"]["name"]
                items_info[idx]["name"] = items["track"]["name"]
                if len(items["track"]["album"]["images"]) > 0:
                    items_info[idx]["thumbnail"] = items["track"]["album"]["images"][0]["url"]
                else:
                    items_info[idx]["thumbnail"] = "/static/icons/favicon-100x100.png"
                items_info[idx]["uri"] = items["track"]["uri"]
                items_info[idx]["mediasource"] = ais_global.G_AN_SPOTIFY
                items_info[idx]["type"] = items["track"]["type"]
                items_info[idx]["icon"] = 'mdi:play'
                idx = idx + 1

        # update list
        self.hass.states.async_set("sensor.spotifylist", 0, items_info)

    @asyncio.coroutine
    def process_search_async(self, call):
        """Search album on Spotify."""
        if "query" not in call.data:
            _LOGGER.error("No text to search")
            return
        global G_SPOTIFY_FOUND
        G_SPOTIFY_FOUND = []
        search_text = call.data["query"]

        self.refresh_spotify_instance()

        # Don't true search when token is expired
        if self._oauth.is_token_expired(self._token_info):
            _LOGGER.warning("Spotify failed to update, token expired.")
            return

        titles = [ais_global.G_EMPTY_OPTION]
        # artist
        results = self._spotify.search(q='artist:' + search_text, type='artist')
        titles.extend(self.get_list_from_results(results, 'artist'))
        # album
        results = self._spotify.search(q='album:' + search_text, type='album')
        titles.extend(self.get_list_from_results(results, 'album'))
        # playlist
        results = self._spotify.search(q='playlist:' + search_text, type='playlist')
        titles.extend(self.get_list_from_results(results, 'playlist'))

        # Update input_select values:
        yield from self.hass.services.async_call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.ais_music_track_name",
                "options": titles})

        if len(G_SPOTIFY_FOUND) > 0:
            text = "Znaleziono: %s, włączam pierwszy: %s" % (
                str(len(G_SPOTIFY_FOUND)), G_SPOTIFY_FOUND[0]["title"])
        else:
            text = "Brak wyników na Spotify dla zapytania %s" % search_text
        yield from self.hass.services.async_call(
            'ais_ai_service', 'say_it', {
                "text": text
            })
        yield from self.hass.services.async_call(
            'input_select',
            'select_option', {
                "entity_id": "input_select.ais_music_track_name",
                "option": G_SPOTIFY_FOUND[0]["title"]})

    def process_select_track_name(self, call):
        _LOGGER.info("process_select_track_name")
        import json
        item_uri = None
        item_type = None
        item_owner_id = None
        item_image_url = None
        # """Search in last search return."""
        name = call.data["name"]
        for item in G_SPOTIFY_FOUND:
            if item["title"] == name:
                item_uri = item["uri"]
                item_type = item["type"]
                item_owner_id = item["item_owner_id"]
                item_image_url = item["thumbnail"]
                _audio_info = json.dumps(
                    {"IMAGE_URL": item["thumbnail"], "NAME": item["title"], "MEDIA_SOURCE": ais_global.G_AN_SPOTIFY})
                break

        if item_uri is not None:
            player_name = self.hass.states.get(
                'input_select.ais_music_player').state
            player = ais_cloud.get_player_data(player_name)
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "audio/mp4",
                    "media_content_id": item_uri
                })
            # set stream image and title
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "ais_info",
                    "media_content_id": _audio_info
                })
            # get tracks for item type
            return run_coroutine_threadsafe(
                self.get_tracks_list_async(item_uri, item_type, item_owner_id, item_image_url), self.hass.loop).result()

    def select_track_uri(self, call):
        import json
        _LOGGER.info("select_track_uri")
        # """play track by id on sensor list."""
        call_id = call.data["id"]
        state = self.hass.states.get('sensor.spotifylist')
        attr = state.attributes
        track = attr.get(int(call_id))

        player_name = self.hass.states.get(
            'input_select.ais_music_player').state
        player = ais_cloud.get_player_data(player_name)
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_type": "audio/mp4",
                "media_content_id": track["uri"]
            })
        # set stream image and title
        _audio_info = json.dumps(
            {"IMAGE_URL": track["thumbnail"], "NAME": track["title"], "MEDIA_SOURCE": ais_global.G_AN_SPOTIFY})
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_type": "ais_info",
                "media_content_id": _audio_info
            })

    def change_play_queue(self, call):
        # info from android app
        _LOGGER.info("change_play_queue")

