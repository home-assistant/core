"""Base classes shared among Ecobee entities."""
from __future__ import annotations

import logging

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class EcobeeBaseEntity:
    """Base methods for Ecobee entities."""

    def __init__(self, thermostat) -> None:
        """Initiate base methods for Ecobee entities."""

        self.thermostat = thermostat

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=ECOBEE_MODEL_TO_NAME.get(self.thermostat["modelNumber"]),
            name=self.thermostat["name"],
        )

    @property
    def available(self):
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]
