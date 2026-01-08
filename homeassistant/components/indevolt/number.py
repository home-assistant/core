"""Number platform for Indevolt integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator = entry.runtime_data

    # Add generation 1 entities
    entities: list[IndevoltNumberEntity] = []

    # Add generation 2 entities (if applicable)
    if entry.data.get("generation", 1) != 1:
        entities.extend(
            [
                DischargeLimitNumber(coordinator, entry),
                MaxACOutputPowerNumber(coordinator, entry),
                InverterInputLimit(coordinator, entry),
                FeedinPowerLimit(coordinator, entry),
            ]
        )

    async_add_entities(entities)


class IndevoltNumberEntity(CoordinatorEntity[IndevoltCoordinator], NumberEntity):
    """Base class for Indevolt number entities."""

    _attr_mode = NumberMode.BOX
    _attr_has_entity_name = True
    coordinator: IndevoltCoordinator

    def __init__(
        self, coordinator: IndevoltCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator

        name_suffix = (self._attr_translation_key or "").replace(" ", "_").lower()
        self._attr_unique_id = f"{config_entry.entry_id}_{name_suffix}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data:
            return self._get_current_value()
        return None

    def _get_write_cjson_point(self) -> str:
        """Get the cJson Point for writing to this entity."""
        raise NotImplementedError

    def _get_current_value(self) -> float | None:
        """Get the current value for this entity."""
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self.coordinator.async_push_data(
                self._get_write_cjson_point(), int(value)
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set %s to %s: %s", self.name, value, err)
            raise


class DischargeLimitNumber(IndevoltNumberEntity):
    """Number entity for Discharge Limit percentage (emergency power / SOC)."""

    _attr_translation_key = "discharge_limit"
    _attr_icon = "mdi:battery-alert"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def _get_write_cjson_point(self) -> str:
        """Get the cJson Point for writing Emergency Power value."""
        return "1142"

    def _get_current_value(self) -> float | None:
        """Get the current Emergency Power value."""
        return self.coordinator.data.get("6105")


class MaxACOutputPowerNumber(IndevoltNumberEntity):
    """Number entity for Max AC Output Power."""

    _attr_translation_key = "max_ac_output_power"
    _attr_icon = "mdi:lightning-bolt"
    _attr_native_min_value = 0
    _attr_native_max_value = 2400
    _attr_native_step = 100
    _attr_native_unit_of_measurement = "W"

    def _get_write_cjson_point(self) -> str:
        """Get the cJson Point for writing Max AC Output Power value."""
        return "1147"

    def _get_current_value(self) -> float | None:
        """Get the current Max AC Output Power value."""
        return self.coordinator.data.get("11011")


class InverterInputLimit(IndevoltNumberEntity):
    """Number entity for Inverter Input Limit."""

    _attr_translation_key = "inverter_input_limit"
    _attr_icon = "mdi:current-dc"
    _attr_native_min_value = 100
    _attr_native_max_value = 2400
    _attr_native_step = 100
    _attr_native_unit_of_measurement = "W"

    def _get_write_cjson_point(self) -> str:
        """Get the cJson Point for writing Inverter Input Limit value."""
        return "1138"

    def _get_current_value(self) -> float | None:
        """Get the current Inverter Input Limit value."""
        return self.coordinator.data.get("11009")


class FeedinPowerLimit(IndevoltNumberEntity):
    """Number entity for Feed-in Power Limit."""

    _attr_translation_key = "feedin_power_limit"
    _attr_icon = "mdi:current-dc"
    _attr_native_min_value = 100
    _attr_native_max_value = 2400
    _attr_native_step = 100
    _attr_native_unit_of_measurement = "W"

    def _get_write_cjson_point(self) -> str:
        """Get the cJson Point for writing Feed-in Power Limit value."""
        return "1146"

    def _get_current_value(self) -> float | None:
        """Get the current Feed-in Power Limit value."""
        return self.coordinator.data.get("11010")
