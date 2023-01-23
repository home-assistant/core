"""Base classes shared among Ecobee entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class EcobeeBaseEntity(Entity):
    """Base methods for Ecobee entities."""

    def __init__(self, thermostat: dict[str, Any]) -> None:
        """Initiate base methods for Ecobee entities."""

        self.thermostat = thermostat
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=ECOBEE_MODEL_TO_NAME.get(thermostat["modelNumber"]),
            name=thermostat["name"],
        )

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]
