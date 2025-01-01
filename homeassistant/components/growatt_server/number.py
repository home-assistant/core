"""Module for Growatt number integration with Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrowattCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GrowattRequiredNumberKey:
    """Mixin for required keys."""

    api_key: str


@dataclass(frozen=True)
class GrowattNumberEntityDescription(NumberEntityDescription, GrowattRequiredNumberKey):
    """Describes Growatt number entity."""


TLX_NUMBER_TYPES: tuple[GrowattNumberEntityDescription, ...] = (
    GrowattNumberEntityDescription(
        api_key="charge_power",
        key="tlx_charge_power",
        translation_key="tlx_charge_power",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.AUTO,
    ),
    GrowattNumberEntityDescription(
        api_key="charge_stop_soc",
        key="tlx_charge_stop_soc",
        translation_key="tlx_charge_stop_soc",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.AUTO,
    ),
    GrowattNumberEntityDescription(
        api_key="discharge_power",
        key="tlx_discharge_power",
        translation_key="tlx_discharge_power",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.AUTO,
    ),
    GrowattNumberEntityDescription(
        api_key="on_grid_discharge_stop_soc",
        key="tlx_discharge_stop_soc",
        translation_key="tlx_discharge_stop_soc",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.AUTO,
    ),
)


class GrowattNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Growatt number."""

    _attr_has_entity_name = True
    coordinator: GrowattCoordinator
    entity_description: GrowattNumberEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        device_name: str,
        serial_id: str,
        unique_id: str,
        description: GrowattNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_id)}, manufacturer="Growatt", name=device_name
        )

    @property
    def native_value(self) -> int:
        """Return the current value of the number."""
        return self.coordinator.get_value(self.entity_description)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        res = await self.hass.async_add_executor_job(
            self.coordinator.api.update_tlx_inverter_setting,
            self.coordinator.device_id,
            self.entity_description.api_key,
            int(value),
        )
        _LOGGER.debug(
            "Set parameter: %s to value: %s, res: %s",
            self.entity_description.key,
            value,
            res,
        )
        if res.get("success"):
            # If success, update single parameter value in coordinator instead of
            # fetching all data with coordinator.async_refresh() to off-load the API
            self.coordinator.set_value(self.entity_description, int(value))
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Set parameter: %s to value: %s failed msg: %s, error: %s",
                self.entity_description.key,
                value,
                res.get("msg"),
                res.get("error"),
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt number."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Add numbers for each device type
    for device_sn, device_coordinator in coordinators["devices"].items():
        if device_coordinator.device_type == "tlx":
            for description in TLX_NUMBER_TYPES:
                entities.extend(
                    [
                        GrowattNumber(
                            device_coordinator,
                            device_name=device_sn,
                            serial_id=device_sn,
                            unique_id=f"{device_sn}-{description.key}",
                            description=description,
                        )
                    ]
                )
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device_coordinator.device_type,
            )

    async_add_entities(entities, True)
