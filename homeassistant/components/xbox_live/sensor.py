"""Sensor for Xbox Live account status."""
from datetime import timedelta
import logging

import voluptuous as vol
from xboxapi import xbox_api

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

CONF_XUID = "xuid"

ICON = "mdi:microsoft-xbox"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_XUID): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Xbox platform."""
    api = xbox_api.XboxApi(config[CONF_API_KEY])
    entities = []

    # request personal profile to check api connection
    profile = api.get_profile()
    if profile.get("error_code") is not None:
        _LOGGER.error(
            "Can't setup XboxAPI connection. Check your account or "
            "api key on xboxapi.com. Code: %s Description: %s ",
            profile.get("error_code", "unknown"),
            profile.get("error_message", "unknown"),
        )
        return

    users = config[CONF_XUID]

    interval = timedelta(minutes=1 * len(users))
    interval = config.get(CONF_SCAN_INTERVAL, interval)

    for xuid in users:
        gamercard = get_user_gamercard(api, xuid)
        if gamercard is None:
            continue
        entities.append(XboxSensor(api, xuid, gamercard, interval))

    if entities:
        add_entities(entities, True)


def get_user_gamercard(api, xuid):
    """Get profile info."""
    gamercard = api.get_user_gamercard(xuid)
    _LOGGER.debug("User gamercard: %s", gamercard)

    if gamercard.get("success", True) and gamercard.get("code") is None:
        return gamercard
    _LOGGER.error(
        "Can't get user profile %s. Error Code: %s Description: %s",
        xuid,
        gamercard.get("code", "unknown"),
        gamercard.get("description", "unknown"),
    )
    return None


class XboxSensor(Entity):
    """A class for the Xbox account."""

    def __init__(self, api, xuid, gamercard, interval):
        """Initialize the sensor."""
        self._state = None
        self._presence = []
        self._xuid = xuid
        self._api = api
        self._gamertag = gamercard.get("gamertag")
        self._gamerscore = gamercard.get("gamerscore")
        self._interval = interval
        self._picture = gamercard.get("gamerpicSmallSslImagePath")
        self._tier = gamercard.get("tier")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._gamertag

    @property
    def should_poll(self):
        """Return False as this entity has custom polling."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        attributes["gamerscore"] = self._gamerscore
        attributes["tier"] = self._tier

        for device in self._presence:
            for title in device.get("titles"):
                attributes[
                    f'{device.get("type")} {title.get("placement")}'
                ] = title.get("name")

        return attributes

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._picture

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    async def async_added_to_hass(self):
        """Start custom polling."""

        @callback
        def async_update(event_time=None):
            """Update the entity."""
            self.async_schedule_update_ha_state(True)

        async_track_time_interval(self.hass, async_update, self._interval)

    def update(self):
        """Update state data from Xbox API."""
        presence = self._api.get_user_presence(self._xuid)
        _LOGGER.debug("User presence: %s", presence)
        self._state = presence.get("state")
        self._presence = presence.get("devices", [])
