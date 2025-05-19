"""Base class shared among IRM KMI entities."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, IRM_KMI_NAME
from .utils import preferred_language

_LOGGER = logging.getLogger(__name__)


class IrmKmiBaseEntity(Entity):
    """Base methods for IRM KMI entities."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init base properties for IRM KMI entities."""
        self._attr_attribution = (
            "Weather data from the Royal Meteorological Institute of Belgium meteo.be"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=IRM_KMI_NAME.get(preferred_language(self.hass, entry)),
            name=entry.title,
        )
