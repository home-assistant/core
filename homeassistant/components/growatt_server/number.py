"""Number platform for Growatt."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from growattServer import GrowattV1ApiError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattConfigEntry, GrowattCoordinator
from .sensor.sensor_entity_description import GrowattRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = (
    1  # Serialize updates as inverter does not handle concurrent requests
)


@dataclass(frozen=True, kw_only=True)
class GrowattNumberEntityDescription(NumberEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt number entity."""

    write_key: str | None = None  # Parameter ID for writing (if different from api_key)


# Note that the Growatt V1 API uses different keys for reading and writing parameters.
# Reading values returns camelCase keys, while writing requires snake_case keys.

MIN_NUMBER_TYPES: tuple[GrowattNumberEntityDescription, ...] = (
    GrowattNumberEntityDescription(
        key="battery_charge_power_limit",
        translation_key="battery_charge_power_limit",
        api_key="chargePowerCommand",  # Key returned by V1 API
        write_key="charge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="battery_charge_soc_limit",
        translation_key="battery_charge_soc_limit",
        api_key="wchargeSOCLowLimit",  # Key returned by V1 API
        write_key="charge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="battery_discharge_power_limit",
        translation_key="battery_discharge_power_limit",
        api_key="disChargePowerCommand",  # Key returned by V1 API
        write_key="discharge_power",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key="battery_discharge_soc_limit",
        translation_key="battery_discharge_soc_limit",
        api_key="wdisChargeSOCLowLimit",  # Key returned by V1 API
        write_key="discharge_stop_soc",  # Key used to write parameter
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Growatt number entities."""
    runtime_data = entry.runtime_data

    # Add number entities for each MIN device (only supported with V1 API)
    async_add_entities(
        GrowattNumber(device_coordinator, description)
        for device_coordinator in runtime_data.devices.values()
        if (
            device_coordinator.device_type == "min"
            and device_coordinator.api_version == "v1"
        )
        for description in MIN_NUMBER_TYPES
    )


class GrowattNumber(CoordinatorEntity[GrowattCoordinator], NumberEntity):
    """Representation of a Growatt number."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    entity_description: GrowattNumberEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        description: GrowattNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    @property
    def native_value(self) -> int | None:
        """Return the current value of the number."""
        value = self.coordinator.data.get(self.entity_description.api_key)
        if value is None:
            return None
        return int(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        # Use write_key if specified, otherwise fall back to api_key
        parameter_id = (
            self.entity_description.write_key or self.entity_description.api_key
        )
        int_value = int(value)

        try:
            # Use V1 API to write parameter
            await self.hass.async_add_executor_job(
                self.coordinator.api.min_write_parameter,
                self.coordinator.device_id,
                parameter_id,
                int_value,
            )
        except GrowattV1ApiError as e:
            raise HomeAssistantError(f"Error while setting parameter: {e}") from e

        # If no exception was raised, the write was successful
        _LOGGER.debug(
            "Set parameter %s to %s",
            parameter_id,
            value,
        )

        # Update the value in coordinator data to avoid triggering an immediate
        # refresh that would hit the API rate limit (5-minute polling interval)
        self.coordinator.data[self.entity_description.api_key] = int_value
        self.async_write_ha_state()
