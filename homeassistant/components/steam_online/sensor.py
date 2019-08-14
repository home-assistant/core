"""Sensor for Steam account status."""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

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
    import steam as steamod

    steamod.api.key.set(config.get(CONF_API_KEY))
    # Initialize steammods app list before creating sensors
    # to benefit from internal caching of the list.
    hass.data[APP_LIST_KEY] = steamod.apps.app_list()
    entities = [SteamSensor(account, steamod) for account in config.get(CONF_ACCOUNTS)]
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
        self._game = self._state = self._name = self._avatar = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return "sensor.steam_{}".format(self._account)

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
        except self._steamod.api.HTTPTimeoutError as error:
            _LOGGER.warning(error)
            self._game = self._state = self._name = self._avatar = None

    def _get_current_game(self):
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

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"game": self._game} if self._game else None

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._avatar

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
