# pylint: disable=duplicate-code
"""Creates Switch entities for the my-PV Home Assistant integration."""

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator
from .const import RESERVED_KEYS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV switch."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    for key, config in coordinator.setup_configurations:
        if config.get("type") == "boolean" and key not in RESERVED_KEYS:
            entity_description = SwitchEntityDescription(
                key=key,
                translation_key=key,
                device_class=SwitchDeviceClass.SWITCH,
            )
            entities.append(
                MyPVSwitch(
                    coordinator,
                    entity_description,
                    config_entry.entry_id,
                )
            )

    async_add_entities(entities)


class MyPVSwitch(CoordinatorEntity, SwitchEntity):
    """Base my-PV Switch."""

    _attr_has_entity_name = True
    _attr_available = False

    coordinator: MyPVCoordinator

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: SwitchEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            value = self.coordinator.get_setup_value(self.entity_description.key)
            if value is None:
                self._attr_available = False
            else:
                self._attr_is_on = bool(value)
                self._attr_available = True

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.set_setup_value(self.entity_description.key, True):
            self._attr_available = True
            self._attr_is_on = True
        else:
            _LOGGER.error("Failed to turn on %s", self.name)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.set_setup_value(self.entity_description.key, False):
            self._attr_available = True
            self._attr_is_on = False
        else:
            _LOGGER.error("Failed to turn off %s", self.name)

        self.async_write_ha_state()
