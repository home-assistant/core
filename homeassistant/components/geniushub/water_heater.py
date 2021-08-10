"""Support for Genius Hub water_heater devices."""
from __future__ import annotations

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, GeniusHeatingZone

STATE_AUTO = "auto"
STATE_MANUAL = "manual"

# Genius Hub HW zones support only Off, Override/Boost & Timer modes
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

GH_HEATERS = ["hot water temperature"]


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the Genius Hub water_heater entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    async_add_entities(
        [
            GeniusWaterHeater(broker, z)
            for z in broker.client.zone_objs
            if z.data["type"] in GH_HEATERS
        ]
    )


class GeniusWaterHeater(GeniusHeatingZone, WaterHeaterEntity):
    """Representation of a Genius Hub water_heater device."""

    def __init__(self, broker, zone) -> None:
        """Initialize the water_heater device."""
        super().__init__(broker, zone)

        self._max_temp = 80.0
        self._min_temp = 30.0
        self._supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return list(HA_OPMODE_TO_GH)

    @property
    def current_operation(self) -> str:
        """Return the current operation mode."""
        return GH_STATE_TO_HA[self._zone.data["mode"]]

    async def async_set_operation_mode(self, operation_mode) -> None:
        """Set a new operation mode for this boiler."""
        await self._zone.set_mode(HA_OPMODE_TO_GH[operation_mode])
