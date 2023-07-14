"""Support for Pocket Casts."""
from __future__ import annotations

from datetime import timedelta
import logging

from pycketcasts import pocketcasts
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


SENSOR_NAME = "Pocketcasts unlistened episodes"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PASSWORD): cv.string, vol.Required(CONF_USERNAME): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pocketcasts platform for sensors."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        api = pocketcasts.PocketCast(email=username, password=password)
        _LOGGER.debug("Found %d podcasts", len(api.subscriptions))
        add_entities([PocketCastsSensor(api)], True)
    except OSError as err:
        _LOGGER.error("Connection to server failed: %s", err)


class PocketCastsSensor(SensorEntity):
    """Representation of a pocket casts sensor."""

    _attr_icon = "mdi:rss"

    def __init__(self, api):
        """Initialize the sensor."""
        self._api = api
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_NAME

    @property
    def native_value(self):
        """Return the sensor state."""
        return self._state

    def update(self) -> None:
        """Update sensor values."""
        try:
            self._state = len(self._api.new_releases)
            _LOGGER.debug("Found %d new episodes", self._state)
        except OSError as err:
            _LOGGER.warning("Failed to contact server: %s", err)
