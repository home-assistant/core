"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from typing import Any, Dict, Optional, List

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up an InComfort/InTouch climate device."""
    client = hass.data[DOMAIN]["client"]
    heater = hass.data[DOMAIN]["heater"]

    async_add_entities([InComfortClimate(client, r) for r in heater.rooms])


class InComfortClimate(ClimateDevice):
    """Representation of an InComfort/InTouch climate device."""

    def __init__(self, client, room):
        """Initialize the climate device."""
        self._client = client
        self._room = room
        self._name = "Room {}".format(room.room_no)

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        return {"status": self._room.status}

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._room.room_temp

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._room.override

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

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

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        pass
