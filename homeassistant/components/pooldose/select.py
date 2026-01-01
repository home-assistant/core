"""Select entities for the Seko PoolDose integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .const import UNIT_MAPPING
from .entity import PooldoseEntity

if TYPE_CHECKING:
    from .coordinator import PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PooldoseSelectEntityDescription(SelectEntityDescription):
    """Describes PoolDose select entity."""

    use_unit_conversion: bool = False


SELECT_DESCRIPTIONS: tuple[PooldoseSelectEntityDescription, ...] = (
    PooldoseSelectEntityDescription(
        key="water_meter_unit",
        translation_key="water_meter_unit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=[UnitOfVolume.LITERS, UnitOfVolume.CUBIC_METERS],
        use_unit_conversion=True,
    ),
    PooldoseSelectEntityDescription(
        key="flow_rate_unit",
        translation_key="flow_rate_unit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=[
            UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            UnitOfVolumeFlowRate.LITERS_PER_SECOND,
        ],
        use_unit_conversion=True,
    ),
    PooldoseSelectEntityDescription(
        key="ph_type_dosing_set",
        translation_key="ph_type_dosing_set",
        entity_category=EntityCategory.CONFIG,
        options=["alcalyne", "acid"],
    ),
    PooldoseSelectEntityDescription(
        key="ph_type_dosing_method",
        translation_key="ph_type_dosing_method",
        entity_category=EntityCategory.CONFIG,
        options=["off", "proportional", "on_off", "timed"],
        entity_registry_enabled_default=False,
    ),
    PooldoseSelectEntityDescription(
        key="orp_type_dosing_set",
        translation_key="orp_type_dosing_set",
        entity_category=EntityCategory.CONFIG,
        options=["low", "high"],
        entity_registry_enabled_default=False,
    ),
    PooldoseSelectEntityDescription(
        key="orp_type_dosing_method",
        translation_key="orp_type_dosing_method",
        entity_category=EntityCategory.CONFIG,
        options=["off", "proportional", "on_off", "timed"],
        entity_registry_enabled_default=False,
    ),
    PooldoseSelectEntityDescription(
        key="cl_type_dosing_set",
        translation_key="cl_type_dosing_set",
        entity_category=EntityCategory.CONFIG,
        options=["low", "high"],
        entity_registry_enabled_default=False,
    ),
    PooldoseSelectEntityDescription(
        key="cl_type_dosing_method",
        translation_key="cl_type_dosing_method",
        entity_category=EntityCategory.CONFIG,
        options=["off", "proportional", "on_off", "timed"],
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose select entities from a config entry."""
    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    coordinator = config_entry.runtime_data
    select_data = coordinator.data["select"]
    serial_number = config_entry.unique_id

    async_add_entities(
        PooldoseSelect(coordinator, serial_number, coordinator.device_info, description)
        for description in SELECT_DESCRIPTIONS
        if description.key in select_data
    )


class PooldoseSelect(PooldoseEntity, SelectEntity):
    """Select entity for the Seko PoolDose Python API."""

    entity_description: PooldoseSelectEntityDescription

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_info: Any,
        description: PooldoseSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, serial_number, device_info, description, "select")
        self._async_update_attrs()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _async_update_attrs(self) -> None:
        """Update select attributes."""
        data = cast(dict, self.get_data())
        api_value = cast(str, data["value"])

        # Convert API value to Home Assistant unit if unit conversion is enabled
        if self.entity_description.use_unit_conversion:
            # Map API value (e.g., "m3") to HA unit (e.g., "m³")
            self._attr_current_option = UNIT_MAPPING.get(api_value, api_value)
        else:
            self._attr_current_option = api_value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Convert Home Assistant unit to API value if unit conversion is enabled
        if self.entity_description.use_unit_conversion:
            # Invert UNIT_MAPPING to get API value from HA unit
            reverse_map = {v: k for k, v in UNIT_MAPPING.items()}
            api_value = reverse_map.get(option, option)
        else:
            api_value = option

        await self._async_perform_write(
            self.coordinator.client.set_select, self.entity_description.key, api_value
        )

        self._attr_current_option = option
        self.async_write_ha_state()
