"""Support for ZoneMinder sensors."""
import logging
from typing import Callable, List, Optional

from zoneminder.zm import ZoneMinder

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import get_config_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    config_data = get_config_data(hass, config_entry)
    async_add_entities([ZMSensorRunState(config_data.client, config_entry)], True)


class ZMSensorRunState(Entity):
    """Get the ZoneMinder run state."""

    def __init__(self, client: ZoneMinder, config_entry: ConfigEntry):
        """Initialize run state sensor."""
        self._state = None
        self._is_available = None
        self._client = client
        self._config_entry = config_entry

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_runstate"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Zoneminder Run State"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if ZoneMinder is available."""
        return self._is_available

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        return {CONF_HOST: self._config_entry.data[CONF_HOST]}

    def update(self):
        """Update the sensor."""
        self._state = self._client.get_active_state()
        self._is_available = self._client.is_available
