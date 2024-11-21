"""Imeon inverter sensor support."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InverterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create each sensor for a given config entry."""

    # Get Inverter from UUID
    IC: InverterCoordinator = entry.runtime_data

    async_add_entities(
        ([InverterSensor(IC, "meter_power", entry, "Meter Power", "W")]), True
    )


class InverterSensor(CoordinatorEntity, SensorEntity):
    """A sensor that returns numerical values with units."""

    def __init__(self, coordinator, data_key, entry, friendly_name, unit) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.data_key = data_key
        self._entry_id = entry.entry_id
        self._namespace = DOMAIN + "." + data_key
        self._device = entry.title

        self._attr_name = friendly_name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = str(unit)
        self._attr_mode = "box"
        self._attr_icon = "mdi:numeric"
        self._attr_unique_id = f"{self._entry_id}_{self.data_key}"
        self._attr_editable = False

        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this entity."""
        # This needs to be strictly identical for every entity
        # so as to have every entity grouped under one single
        # device in the integration menu.
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._device,
            manufacturer="Imeon Energy",
            model="Home Assistant Integration",
            sw_version="1.0",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            fetched = float(self.coordinator.data.get(self.data_key, None))
            if self._attr_native_value == fetched:
                return
            self._attr_native_value = fetched
        except (TypeError, ValueError):
            self._attr_native_value = None  # N/A

        # Request a data update
        self.async_write_ha_state()
        return
