"""Support for SleepIQ buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SLEEPIQ_DATA
from .device import SleepNumberEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep number switches."""
    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]

    entities: list[SleepNumberEntity] = []
    for bed in data.beds.values():
        entities.append(SleepNumberCalibrateButton(bed))
        entities.append(SleepNumberStopPumpButton(bed))

    async_add_entities(entities)


class SleepNumberCalibrateButton(SleepNumberEntity, ButtonEntity):
    """Representation of an SleepIQ privacy mode."""

    def __init__(self, bed):
        super().__init__(bed)
        self._attr_name = f"{bed.name} Calibrate"
        self._attr_unique_id = f"{bed.id}-Calibrate"

    async def async_press(self) -> None:
        """Press the button."""
        await self._bed.calibrate()


class SleepNumberStopPumpButton(SleepNumberEntity, ButtonEntity):
    """Representation of an SleepIQ privacy mode."""

    def __init__(self, bed):
        super().__init__(bed)
        self._attr_name = f"{bed.name} Stop Pump"
        self._attr_unique_id = f"{bed.id}-StopPump"

    async def async_press(self) -> None:
        """Press the button."""
        await self._bed.stop_pump()
