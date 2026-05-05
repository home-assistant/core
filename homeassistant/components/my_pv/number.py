# pylint: disable=duplicate-code
"""Creates Number entities for the my-PV Home Assistant integration."""

import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator
from .const import NUMBER_DEVICE_CLASSES, RESERVED_KEYS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV number."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    for key, config in coordinator.setup_configurations:
        if config.get("type") == "number" and key not in RESERVED_KEYS:
            device_class = NUMBER_DEVICE_CLASSES.get(key)
            entity_description = NumberEntityDescription(
                key=key,
                translation_key=key,
                device_class=device_class,
                native_unit_of_measurement=config.get("unit"),
                native_min_value=config.get("min", 0),
                native_max_value=config.get("max"),
                native_step=config.get("step"),
            )
            entities.append(
                MyPVNumber(
                    coordinator,
                    entity_description,
                    config_entry.entry_id,
                )
            )

    async_add_entities(entities)


class MyPVNumber(CoordinatorEntity, NumberEntity):
    """Base my-PV Number."""

    _attr_has_entity_name = True
    _attr_available = False

    coordinator: MyPVCoordinator

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: NumberEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the number."""
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
                self._attr_native_value = float(value)
                self._attr_available = True

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        _LOGGER.debug("Setting %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.set_setup_value(self.entity_description.key, value):
            self._attr_available = True
            self._attr_native_value = value
        else:
            _LOGGER.error("Failed to set %s", self.name)

        self.async_write_ha_state()
