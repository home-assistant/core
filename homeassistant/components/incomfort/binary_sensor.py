"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from typing import Any

from incomfortclient import Gateway as InComfortGateway, Heater as InComfortHeater

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_INCOMFORT, IncomfortEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an InComfort/InTouch binary_sensor entity."""
    incomfort_data = hass.data[DATA_INCOMFORT][entry.entry_id]
    async_add_entities(
        IncomfortFailed(incomfort_data.client, h) for h in incomfort_data.heaters
    )


class IncomfortFailed(IncomfortEntity, BinarySensorEntity):
    """Representation of an InComfort Failed sensor."""

    _attr_name = "Fault"

    def __init__(self, client: InComfortGateway, heater: InComfortHeater) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._client = client
        self._heater = heater

        self._attr_unique_id = f"{heater.serial_no}_failed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heater.serial_no)},
            manufacturer="Intergas",
            name="Boiler",
        )

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._heater.status["is_failed"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        return {"fault_code": self._heater.status["fault_code"]}
