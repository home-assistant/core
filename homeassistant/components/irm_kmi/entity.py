"""Base class shared among IRM KMI entities."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IRM_KMI_NAME
from .utils import preferred_language

_LOGGER = logging.getLogger(__name__)


class IrmKmiBaseEntity(CoordinatorEntity):
    """Base methods for IRM KMI entities."""

    _attr_attribution = (
        "Weather data from the Royal Meteorological Institute of Belgium meteo.be"
    )

    def __init__(self, entry: ConfigEntry, name: str) -> None:
        """Init base properties for IRM KMI entities."""
        coordinator = entry.runtime_data.coordinator
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=IRM_KMI_NAME.get(preferred_language(self.hass, entry)),
            name=name,
        )
