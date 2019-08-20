"""Support for Genius Hub water_heater devices."""
from typing import Any, Awaitable, Dict, Optional, List

from homeassistant.components.water_heater import (
    WaterHeaterDevice,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS

from . import DOMAIN, GeniusEntity

STATE_AUTO = "auto"
STATE_MANUAL = "manual"

GH_HEATERS = ["hot water temperature"]

GH_SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
# HA does not have SUPPORT_ON_OFF for water_heater

GH_MAX_TEMP = 80.0
GH_MIN_TEMP = 30.0

# Genius Hub HW supports only Off, Override/Boost & Timer modes
HA_OPMODE_TO_GH = {STATE_OFF: "off", STATE_AUTO: "timer", STATE_MANUAL: "override"}
GH_STATE_TO_HA = {
    "off": STATE_OFF,
    "timer": STATE_AUTO,
    "footprint": None,
    "away": None,
    "override": STATE_MANUAL,
    "early": None,
    "test": None,
    "linked": None,
    "other": None,
}
GH_STATE_ATTRS = ["type", "override"]


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the Genius Hub water_heater entities."""
    client = hass.data[DOMAIN]["client"]

    entities = [
        GeniusWaterHeater(z) for z in client.zone_objs if z.data["type"] in GH_HEATERS
    ]

    async_add_entities(entities)


class GeniusWaterHeater(GeniusEntity, WaterHeaterDevice):
    """Representation of a Genius Hub water_heater device."""

    def __init__(self, boiler) -> None:
        """Initialize the water_heater device."""
        super().__init__()

        self._boiler = boiler
        self._operation_list = list(HA_OPMODE_TO_GH)

    @property
    def name(self) -> str:
        """Return the name of the water_heater device."""
        return self._boiler.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        return {
            "status": {
                k: v for k, v in self._boiler.data.items() if k in GH_STATE_ATTRS
            }
        }

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._boiler.data.get("temperature")

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._boiler.data["setpoint"]

    @property
    def min_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return GH_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return GH_MAX_TEMP

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return GH_SUPPORT_FLAGS

    @property
    def operation_list(self) -> List[str]:
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def current_operation(self) -> str:
        """Return the current operation mode."""
        return GH_STATE_TO_HA[self._boiler.data["mode"]]

    async def async_set_operation_mode(self, operation_mode) -> Awaitable[None]:
        """Set a new operation mode for this boiler."""
        await self._boiler.set_mode(HA_OPMODE_TO_GH[operation_mode])

    async def async_set_temperature(self, **kwargs) -> Awaitable[None]:
        """Set a new target temperature for this boiler."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self._boiler.set_override(temperature, 3600)  # 1 hour
