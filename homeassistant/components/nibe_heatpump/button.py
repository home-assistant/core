"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from dataclasses import dataclass

from nibe.exceptions import CoilNotFoundException
from nibe.heatpump import Series

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, LOGGER, Coordinator


@dataclass
class AlarmResetDescriptionMixin:
    """Mixin for required fields."""

    alarm_reset: int
    alarm: int


@dataclass
class AlarmResetDescription(ButtonEntityDescription, AlarmResetDescriptionMixin):
    """Base description."""


RESET_BUTTONS_F = (
    AlarmResetDescription(
        key="reset-alarm",
        name="Reset Alarm",
        alarm_reset=45171,
        alarm=45001,
    ),
)

RESET_BUTTONS_S = (
    AlarmResetDescription(
        key="reset-alarm",
        name="Reset Alarm",
        alarm_reset=40023,
        alarm=31976,
    ),
)

RESET_BUTTONS = {
    Series.F: RESET_BUTTONS_F,
    Series.S: RESET_BUTTONS_S,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    def reset_buttons():
        for entity_description in RESET_BUTTONS.get(coordinator.series, ()):
            try:
                yield NibeAlarmResetButton(coordinator, entity_description)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping button %r", exception)

    async_add_entities(reset_buttons())


class NibeAlarmResetButton(CoordinatorEntity[Coordinator], ButtonEntity):
    """Sensor entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: AlarmResetDescription

    def __init__(
        self, coordinator: Coordinator, entity_description: AlarmResetDescription
    ) -> None:
        """Initialize entity."""
        self._reset_coil = coordinator.heatpump.get_coil_by_address(
            entity_description.alarm_reset
        )
        self._alarm_coil = coordinator.heatpump.get_coil_by_address(
            entity_description.alarm
        )
        super().__init__(coordinator, {self._alarm_coil.address})
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.unique_id}-{entity_description.key}"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Execute the command."""
        await self.coordinator.async_write_coil(self._reset_coil, 1)
        await self.coordinator.async_read_coil(self._alarm_coil)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if coil := self.coordinator.data.get(self._alarm_coil.address):
            return coil.value != 0

        return False
