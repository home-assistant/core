"""Number entities for the Seko PoolDose integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .entity import PooldoseEntity

if TYPE_CHECKING:
    from .coordinator import PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="ph_target",
        translation_key="ph_target",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.PH,
    ),
    NumberEntityDescription(
        key="orp_target",
        translation_key="orp_target",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    NumberEntityDescription(
        key="cl_target",
        translation_key="cl_target",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    NumberEntityDescription(
        key="ofa_ph_lower",
        translation_key="ofa_ph_lower",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.PH,
    ),
    NumberEntityDescription(
        key="ofa_ph_upper",
        translation_key="ofa_ph_upper",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.PH,
    ),
    NumberEntityDescription(
        key="ofa_orp_lower",
        translation_key="ofa_orp_lower",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    NumberEntityDescription(
        key="ofa_orp_upper",
        translation_key="ofa_orp_upper",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    NumberEntityDescription(
        key="ofa_cl_lower",
        translation_key="ofa_cl_lower",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    NumberEntityDescription(
        key="ofa_cl_upper",
        translation_key="ofa_cl_upper",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose number entities from a config entry."""
    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    coordinator = config_entry.runtime_data
    number_data = coordinator.data.get("number", {})
    serial_number = config_entry.unique_id

    async_add_entities(
        PooldoseNumber(coordinator, serial_number, coordinator.device_info, description)
        for description in NUMBER_DESCRIPTIONS
        if description.key in number_data
    )


class PooldoseNumber(PooldoseEntity, NumberEntity):
    """Number entity for the Seko PoolDose Python API."""

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_info: Any,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, serial_number, device_info, description, "number")
        self._async_update_attrs()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _async_update_attrs(self) -> None:
        """Update number attributes."""
        data = cast(dict, self.get_data())
        self._attr_native_value = data["value"]
        self._attr_native_min_value = data["min"]
        self._attr_native_max_value = data["max"]
        self._attr_native_step = data["step"]

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._async_perform_write(
            self.coordinator.client.set_number, self.entity_description.key, value
        )

        self._attr_native_value = value
        self.async_write_ha_state()
