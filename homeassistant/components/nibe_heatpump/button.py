"""The Nibe Heat Pump sensors."""

from __future__ import annotations

from nibe.coil_groups import UNIT_COILGROUPS, UnitCoilGroup
from nibe.exceptions import CoilNotFoundException

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import CoilCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: CoilCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    def reset_buttons():
        if unit := UNIT_COILGROUPS.get(coordinator.series, {}).get("main"):
            try:
                yield NibeAlarmResetButton(coordinator, unit)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping button %r", exception)

    async_add_entities(reset_buttons())


class NibeAlarmResetButton(CoordinatorEntity[CoilCoordinator], ButtonEntity):
    """Sensor entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoilCoordinator, unit: UnitCoilGroup) -> None:
        """Initialize entity."""
        self._reset_coil = coordinator.heatpump.get_coil_by_address(unit.alarm_reset)
        self._alarm_coil = coordinator.heatpump.get_coil_by_address(unit.alarm)
        super().__init__(coordinator, {self._alarm_coil.address})
        self._attr_name = self._reset_coil.title
        self._attr_unique_id = f"{coordinator.unique_id}-alarm_reset"
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
