"""Base classes shared among Ecobee entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import EcobeeData
from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class EcobeeBaseEntity(Entity):
    """Base methods for Ecobee entities."""

    def __init__(self, data: EcobeeData, thermostat_index: int) -> None:
        """Initiate base methods for Ecobee entities."""
        self.data = data
        self.thermostat_index = thermostat_index
        thermostat = self.thermostat
        self.base_unique_id = thermostat["identifier"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=ECOBEE_MODEL_TO_NAME.get(thermostat["modelNumber"]),
            name=thermostat["name"],
        )

    @property
    def thermostat(self) -> dict[str, Any]:
        """Return the thermostat data for the entity."""
        return self.data.ecobee.get_thermostat(self.thermostat_index)

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]
