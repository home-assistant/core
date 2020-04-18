"""Sensor for Steam account status."""
from datetime import timedelta
import logging
from time import mktime

import steam
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utc_from_timestamp

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = "accounts"

ICON = "mdi:steam"

STATE_OFFLINE = "offline"
STATE_ONLINE = "online"
STATE_BUSY = "busy"
STATE_AWAY = "away"
STATE_SNOOZE = "snooze"
STATE_LOOKING_TO_TRADE = "looking_to_trade"
STATE_LOOKING_TO_PLAY = "looking_to_play"

STEAM_API_URL = "https://steamcdn-a.akamaihd.net/steam/apps/"
STEAM_HEADER_IMAGE_FILE = "header.jpg"
STEAM_MAIN_IMAGE_FILE = "capsule_616x353.jpg"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ACCOUNTS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

APP_LIST_KEY = "steam_online.app_list"
BASE_INTERVAL = timedelta(minutes=1)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Steam platform."""

    steam.api.key.set(config.get(CONF_API_KEY))
    # Initialize steammods app list before creating sensors
    # to benefit from internal caching of the list.
    hass.data[APP_LIST_KEY] = steam.apps.app_list()
    entities = [SteamSensor(account, steam) for account in config.get(CONF_ACCOUNTS)]
    if not entities:
        return
    add_entities(entities, True)

    # Only one sensor update once every 60 seconds to avoid
    # flooding steam and getting disconnected.
    entity_next = 0

    @callback
    def do_update(time):
        nonlocal entity_next
        entities[entity_next].async_schedule_update_ha_state(True)
        entity_next = (entity_next + 1) % len(entities)

    async_track_time_interval(hass, do_update, BASE_INTERVAL)


class SteamSensor(Entity):
    """A class for the Steam account."""

    def __init__(self, account, steamod):
        """Initialize the sensor."""
        self._steamod = steamod
        self._account = account
        self._profile = None
        self._game = None
        self._game_id = None
        self._state = None
        self._name = None
        self._avatar = None
        self._last_online = None
        self._level = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return f"sensor.steam_{self._account}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Turn off polling, will do ourselves."""
        return False

    def update(self):
        """Update device state."""
        try:
            self._profile = self._steamod.user.profile(self._account)
            self._game = self._get_current_game()
            self._game_id = self._profile.current_game[0]
            self._state = {
                1: STATE_ONLINE,
                2: STATE_BUSY,
                3: STATE_AWAY,
                4: STATE_SNOOZE,
                5: STATE_LOOKING_TO_TRADE,
                6: STATE_LOOKING_TO_PLAY,
            }.get(self._profile.status, STATE_OFFLINE)
            self._name = self._profile.persona
            self._avatar = self._profile.avatar_medium
            self._last_online = self._get_last_online()
            self._level = self._profile.level
        except self._steamod.api.HTTPTimeoutError as error:
            _LOGGER.warning(error)
            self._game = None
            self._game_id = None
            self._state = None
            self._name = None
            self._avatar = None
            self._last_online = None
            self._level = None

    def _get_current_game(self):
        """Gather current game name from APP ID."""
        game_id = self._profile.current_game[0]
        game_extra_info = self._profile.current_game[2]

        if game_extra_info:
            return game_extra_info

        if not game_id:
            return None

        app_list = self.hass.data[APP_LIST_KEY]
        try:
            _, res = app_list[game_id]
            return res
        except KeyError:
            pass

        # Try reloading the app list, must be a new app
        app_list = self._steamod.apps.app_list()
        self.hass.data[APP_LIST_KEY] = app_list
        try:
            _, res = app_list[game_id]
            return res
        except KeyError:
            pass

        _LOGGER.error("Unable to find name of app with ID=%s", game_id)
        return repr(game_id)

    def _get_last_online(self):
        """Convert last_online from the steam module into timestamp UTC."""
        last_online = utc_from_timestamp(mktime(self._profile.last_online))

        if last_online:
            return last_online

        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self._game is not None:
            attr["game"] = self._game
        if self._game_id is not None:
            attr["game_id"] = self._game_id
            game_url = f"{STEAM_API_URL}{self._game_id}/"
            attr["game_image_header"] = f"{game_url}{STEAM_HEADER_IMAGE_FILE}"
            attr["game_image_main"] = f"{game_url}{STEAM_MAIN_IMAGE_FILE}"
        if self._last_online is not None:
            attr["last_online"] = self._last_online
        if self._level is not None:
            attr["level"] = self._level
        return attr

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._avatar

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
