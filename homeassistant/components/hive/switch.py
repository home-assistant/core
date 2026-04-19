"""Support for the Hive switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HiveConfigEntry, refresh_system
from .const import ATTR_MODE
from .coordinator import HiveDataUpdateCoordinator
from .entity import HiveEntity


SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="activeplug",
    ),
    SwitchEntityDescription(
        key="Heating_Heat_On_Demand",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""

    coordinator = entry.runtime_data
    devices = coordinator.hive.session.deviceList.get("switch")
    if not devices:
        return
    async_add_entities(
        (
            HiveSwitch(coordinator, dev, description)
            for dev in devices
            for description in SWITCH_TYPES
            if dev["hiveType"] == description.key
        ),
        True,
    )


class HiveSwitch(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    def __init__(
        self,
        coordinator: HiveDataUpdateCoordinator,
        hive_device: dict[str, Any],
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialise hive switch."""
        super().__init__(coordinator, hive_device)
        self.entity_description = entity_description

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hive.switch.turnOn(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.hive.switch.turnOff(self.device)

    @callback
    def _update_state_from_device(self) -> None:
        """Update switch attributes from device data."""
        self.attributes.update(self.device.get("attributes", {}))
        self._attr_extra_state_attributes = {ATTR_MODE: self.attributes.get(ATTR_MODE)}
        if self.available:
            self._attr_is_on = self.device["status"]["state"]
