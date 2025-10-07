"""Switch platform for Growatt."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from growattServer import GrowattV1ApiError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
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
class GrowattSwitchEntityDescription(SwitchEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt switch entity."""

    write_key: str | None = None  # Parameter ID for writing (if different from api_key)


# Note that the Growatt V1 API uses different keys for reading and writing parameters.
# Reading values returns camelCase keys, while writing requires snake_case keys.

MIN_SWITCH_TYPES: tuple[GrowattSwitchEntityDescription, ...] = (
    GrowattSwitchEntityDescription(
        key="ac_charge",
        translation_key="ac_charge",
        api_key="acChargeEnable",  # Key returned by V1 API
        write_key="ac_charge",  # Key used to write parameter
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrowattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Growatt switch entities."""
    runtime_data = entry.runtime_data

    entities: list[GrowattSwitch] = []

    # Add switch entities for each MIN device (only supported with V1 API)
    for device_coordinator in runtime_data.devices.values():
        if (
            device_coordinator.device_type == "min"
            and device_coordinator.api_version == "v1"
        ):
            entities.extend(
                GrowattSwitch(
                    coordinator=device_coordinator,
                    description=description,
                )
                for description in MIN_SWITCH_TYPES
            )

    async_add_entities(entities)


class GrowattSwitch(CoordinatorEntity[GrowattCoordinator], SwitchEntity):
    """Representation of a Growatt switch."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    entity_description: GrowattSwitchEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        description: GrowattSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Growatt",
            name=coordinator.device_id,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        value = self.coordinator.data.get(self.entity_description.api_key)
        if value is None:
            return None

        # API returns integer 1 for enabled, 0 for disabled
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state(False)

    async def _async_set_state(self, state: bool) -> None:
        """Set the switch state."""
        # Use write_key if specified, otherwise fall back to api_key
        parameter_id = (
            self.entity_description.write_key or self.entity_description.api_key
        )
        # Convert boolean to API format (1 or 0)
        api_value = 1 if state else 0

        try:
            # Use V1 API to write parameter
            await self.hass.async_add_executor_job(
                self.coordinator.api.min_write_parameter,
                self.coordinator.device_id,
                parameter_id,
                api_value,
            )
        except GrowattV1ApiError as e:
            _LOGGER.error("Error while setting switch state: %s", e)
            raise HomeAssistantError(f"Error while setting switch state: {e}") from e

        # If no exception was raised, the write was successful
        _LOGGER.debug(
            "Set switch %s to %s",
            parameter_id,
            api_value,
        )

        # Update the value in coordinator data (keep as integer like API returns)
        self.coordinator.data[self.entity_description.api_key] = api_value
        self.async_write_ha_state()
