"""Support for SleepIQ buttons."""
from __future__ import annotations

from asyncsleepiq import SleepIQBed

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SleepIQDataUpdateCoordinator
from .entity import SleepIQEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep number buttons."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SleepIQEntity] = []
    for bed in coordinator.client.beds.values():
        entities.append(SleepNumberCalibrateButton(bed))
        entities.append(SleepNumberStopPumpButton(bed))

    async_add_entities(entities)


class SleepNumberCalibrateButton(SleepIQEntity, ButtonEntity):
    """Representation of an SleepIQ calibrate button."""

    def __init__(self, bed: SleepIQBed) -> None:
        """Initialize the Button."""
        super().__init__(bed)
        self._attr_name = f"SleepNumber {bed.name} Calibrate"
        self._attr_unique_id = f"{bed.id}-calibrate"

    async def async_press(self) -> None:
        """Press the button."""
        await self.bed.calibrate()


class SleepNumberStopPumpButton(SleepIQEntity, ButtonEntity):
    """Representation of an SleepIQ stop pump button."""

    def __init__(self, bed: SleepIQBed) -> None:
        """Initialize the Button."""
        super().__init__(bed)
        self._attr_name = f"SleepNumber {bed.name} Stop Pump"
        self._attr_unique_id = f"{bed.id}-stop_pump"

    async def async_press(self) -> None:
        """Press the button."""
        await self.bed.stop_pump()
