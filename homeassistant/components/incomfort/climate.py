"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, IncomfortChild


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an InComfort/InTouch climate device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    async_add_entities(
        [InComfortClimate(client, h, r) for h in heaters for r in h.rooms]
    )


class InComfortClimate(IncomfortChild, ClimateEntity):
    """Representation of an InComfort/InTouch climate device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, client, heater, room) -> None:
        """Initialize the climate device."""
        super().__init__()

        self._unique_id = f"{heater.serial_no}_{room.room_no}"
        self.entity_id = f"{CLIMATE_DOMAIN}.{DOMAIN}_{room.room_no}"
        self._name = f"Thermostat {room.room_no}"

        self._client = client
        self._room = room

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {"status": self._room.status}

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._room.room_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._room.setpoint

    @property
    def min_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return 5.0

    @property
    def max_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return 30.0

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for this zone."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._room.set_override(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
