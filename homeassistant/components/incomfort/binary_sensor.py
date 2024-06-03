"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from typing import Any

from incomfortclient import Gateway as InComfortGateway, Heater as InComfortHeater

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, IncomfortEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an InComfort/InTouch binary_sensor device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    async_add_entities([IncomfortFailed(client, h) for h in heaters])


class IncomfortFailed(IncomfortEntity, BinarySensorEntity):
    """Representation of an InComfort Failed sensor."""

    _attr_name = "Fault"

    def __init__(self, client: InComfortGateway, heater: InComfortHeater) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._client = client
        self._heater = heater

        self._attr_unique_id = f"{heater.serial_no}_failed"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._heater.status["is_failed"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        return {"fault_code": self._heater.status["fault_code"]}
