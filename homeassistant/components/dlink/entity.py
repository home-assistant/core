"""Entity representing a D-Link Power Plug device."""
from __future__ import annotations

from datetime import datetime
import logging
import urllib

from pyW215.pyW215 import SmartPlug

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class SmartPlugData:
    """Get the latest data from smart plug."""

    def __init__(self, smartplug: SmartPlug) -> None:
        """Initialize the data object."""
        self.smartplug = smartplug
        self.state: str | None = None
        self.temperature: float | None = None
        self.current_consumption = None
        self.total_consumption: str | None = None
        self.available = False
        self._n_tried = 0
        self._last_tried: datetime | None = None

    def update(self) -> None:
        """Get the latest data from the smart plug."""
        if self._last_tried is not None:
            last_try_s = (dt_util.now() - self._last_tried).total_seconds() / 60
            retry_seconds = min(self._n_tried * 2, 10) - last_try_s
            if self._n_tried > 0 and retry_seconds > 0:
                _LOGGER.warning("Waiting %s s to retry", retry_seconds)
                return

        _state = "unknown"

        try:
            self._last_tried = dt_util.now()
            _state = self.smartplug.state
        except urllib.error.HTTPError:
            _LOGGER.error("D-Link connection problem")
        if _state == "unknown":
            self._n_tried += 1
            self.available = False
            _LOGGER.warning("Failed to connect to D-Link switch")
            return

        self.state = _state
        self.available = True

        self.temperature = self.smartplug.temperature
        self.current_consumption = self.smartplug.current_consumption
        self.total_consumption = self.smartplug.total_consumption
        self._n_tried = 0


class DLinkEntity(Entity):
    """Representation of a D-Link Power Plug entity."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        data: SmartPlugData,
        config_entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a D-Link Power Plug entity."""
        self.data = data
        self.entity_description = description
        if config_entry.source == SOURCE_IMPORT:
            self._attr_name = config_entry.title
        else:
            self._attr_name = f"{config_entry.title}_{description.key}"
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=config_entry.title,
        )
        if config_entry.unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, config_entry.unique_id)
            }
