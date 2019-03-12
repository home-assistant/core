"""
Support for interacting with Spotify.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.spotify/
"""
import logging
import asyncio
from homeassistant.ais_dom import ais_global
from homeassistant.components import ais_cloud
from homeassistant.core import callback

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

CONFIGURATOR_DESCRIPTION = 'Aby połączyć swoje konto Spotify, kliknij link:'
CONFIGURATOR_LINK_NAME = 'Połącz konto Spotify'
CONFIGURATOR_SUBMIT_CAPTION = 'OK, dostęp dodany!'

DEFAULT_CACHE_PATH = '.dom/.ais-dom-spotify-token-cache'
DEFAULT_NAME = 'Spotify'
DEPENDENCIES = ['http']
DOMAIN = 'ais_spotify_service'

ICON = 'mdi:spotify'

SCOPE = 'app-remote-control streaming user-read-email'
G_SPOTIFY_FOUND = []
_CONFIGURING = {}


def async_setup_spotify(hass, config, configurator):
    """Set up the Spotify platform."""
    import spotipy.oauth2
    import json
    global AIS_SPOTIFY_TOKEN, CONFIGURATOR_DESCRIPTION

    # CONFIGURATOR_DESCRIPTION = 'Niestety coś poszło nie tak. Aby połączyć swoje konto Spotify, kliknij link:'

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
        return False

    cache = hass.config.path(DEFAULT_CACHE_PATH)
    gate_id = ais_global.get_sercure_android_id_dom()
    oauth = spotipy.oauth2.SpotifyOAuth(spotify_client_id, spotify_client_secret, spotify_redirect_url,
                                        scope=spotify_scope, cache_path=cache, state=gate_id)
    token_info = oauth.get_cached_token()
    if not token_info:
        _LOGGER.info("no spotify token in cache;")
        if AIS_SPOTIFY_TOKEN is not None:
            with open(cache, 'w') as outfile:
                json.dump(AIS_SPOTIFY_TOKEN, outfile)
            token_info = oauth.get_cached_token()
        if not token_info:
            _LOGGER.info("no spotify token; run configurator")
            async_request_configuration(hass, config, oauth)
            return

    # register services
    data = hass.data[DOMAIN] = SpotifyData(hass, oauth)

    @asyncio.coroutine
    def search(call):
        _LOGGER.info("search")
        yield from data.process_search_async(call)

    def select_track_name(call):
        _LOGGER.info("select_track_name")
        data.process_select_track_name(call)

    hass.services.async_register(DOMAIN, 'search', search)
    hass.services.async_register(DOMAIN, 'select_track_name', select_track_name)

    return True

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
        return False

    cache = hass.config.path(DEFAULT_CACHE_PATH)
    gate_id = ais_global.get_sercure_android_id_dom()
    oauth = spotipy.oauth2.SpotifyOAuth(spotify_client_id, spotify_client_secret, spotify_redirect_url,
                                        scope=spotify_scope, cache_path=cache, state=gate_id)
    token_info = oauth.get_cached_token()
    if not token_info:
        _LOGGER.info("no spotify token in cache;")
        if AIS_SPOTIFY_TOKEN is not None:
            with open(cache, 'w') as outfile:
                json.dump(AIS_SPOTIFY_TOKEN, outfile)
            token_info = oauth.get_cached_token()
        if not token_info:
            _LOGGER.info("no spotify token; run configurator")
            async_request_configuration(hass, config, oauth)
            return True

    if hass.data.get(DOMAIN):
        configurator = hass.components.configurator
        configurator.request_done(hass.data.get(DOMAIN))
        del hass.data[DOMAIN]

    # register services
    data = hass.data[DOMAIN] = SpotifyData(hass, oauth)

    @asyncio.coroutine
    def search(call):
        _LOGGER.info("search " + str(call))
        yield from data.process_search_async(call)

    def select_track_name(call):
        _LOGGER.info("select_track_name")
        data.process_select_track_name(call)

    hass.services.async_register(DOMAIN, 'search', search)
    hass.services.async_register(DOMAIN, 'select_track_name', select_track_name)

    return True


@callback
def async_request_configuration(hass, config, oauth):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    async def async_configuration_callback(data):
        """Handle configuration changes."""
        _LOGGER.info('Spotify async_configuration_callback')

        def success():
            """Signal successful setup."""
            req_config = _CONFIGURING.pop(oauth.client_id)
            configurator.request_done(req_config)

        hass.async_add_job(success)
        async_setup_spotify(hass, config, configurator)

    _CONFIGURING[oauth.client_id] = configurator.async_request_config(
        DEFAULT_NAME,
        async_configuration_callback,
        link_name=CONFIGURATOR_LINK_NAME,
        link_url=oauth.get_authorize_url(),
        description=CONFIGURATOR_DESCRIPTION,
        submit_caption=CONFIGURATOR_SUBMIT_CAPTION
    )


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
            i = {"uri": item['uri'], "title": title_prefix + name}
            if len(item['images']) > 0:
                i["thumbnail"] = item['images'][0]['url']
            else:
                i["thumbnail"] = ""
            titles.append(title_prefix + name)
            G_SPOTIFY_FOUND.append(i)
        return titles


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
            text = "Brak wnyników na Spotify dla zapytania %s" % search_text
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
        # """Search in last search return."""
        name = call.data["name"]
        for item in G_SPOTIFY_FOUND:
            if item["title"] == name:
                item_uri = item["uri"]
                _audio_info = json.dumps(
                    {"IMAGE_URL": item["thumbnail"], "NAME": item["title"], "MEDIA_SOURCE": ais_global.G_AN_SPOTIFY}
                )

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

