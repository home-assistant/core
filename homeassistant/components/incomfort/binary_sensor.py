"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)

from . import DOMAIN, IncomfortChild


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an InComfort/InTouch binary_sensor device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    async_add_entities([IncomfortFailed(client, h) for h in heaters])


class IncomfortFailed(IncomfortChild, BinarySensorEntity):
    """Representation of an InComfort Failed sensor."""

    def __init__(self, client, heater) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._unique_id = f"{heater.serial_no}_failed"
        self.entity_id = f"{BINARY_SENSOR_DOMAIN}.{DOMAIN}_failed"
        self._name = "Boiler Fault"

        self._client = client
        self._heater = heater

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._heater.status["is_failed"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        return {"fault_code": self._heater.status["fault_code"]}
