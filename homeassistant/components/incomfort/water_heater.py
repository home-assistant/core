"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
from incomfortclient import Gateway as InComfortGateway, Heater as InComfortHeater

from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, IncomfortEntity

_LOGGER = logging.getLogger(__name__)

HEATER_ATTRS = ["display_code", "display_text", "is_burning"]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an InComfort/Intouch water_heater device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    async_add_entities([IncomfortWaterHeater(client, h) for h in heaters])


class IncomfortWaterHeater(IncomfortEntity, WaterHeaterEntity):
    """Representation of an InComfort/Intouch water_heater device."""

    _attr_min_temp = 30.0
    _attr_max_temp = 80.0
    _attr_name = "Boiler"
    _attr_should_poll = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, client: InComfortGateway, heater: InComfortHeater) -> None:
        """Initialize the water_heater device."""
        super().__init__()

        self._client = client
        self._heater = heater

        self._attr_unique_id = heater.serial_no

    @property
    def icon(self) -> str:
        """Return the icon of the water_heater device."""
        return "mdi:thermometer-lines"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {k: v for k, v in self._heater.status.items() if k in HEATER_ATTRS}

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self._heater.is_tapping:
            return self._heater.tap_temp
        if self._heater.is_pumping:
            return self._heater.heater_temp
        return max(self._heater.heater_temp, self._heater.tap_temp)

    @property
    def current_operation(self) -> str:
        """Return the current operation mode."""
        if self._heater.is_failed:
            return f"Fault code: {self._heater.fault_code}"

        return self._heater.display_text

    async def async_update(self) -> None:
        """Get the latest state data from the gateway."""
        try:
            await self._heater.update()

        except (ClientResponseError, TimeoutError) as err:
            _LOGGER.warning("Update failed, message is: %s", err)

        else:
            async_dispatcher_send(self.hass, DOMAIN)
