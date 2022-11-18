"""Kostal Piko sensors."""
import logging

import kostal

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PikoUpdateCoordinator
from .const import DOMAIN, SENSOR_TYPES, KostalPikoEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Kostal Piko platform with its sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    device_info = DeviceInfo(
        configuration_url=entry.data[CONF_HOST],
        identifiers={(DOMAIN, coordinator.data[kostal.InfoVersions.SERIAL_NUMBER])},
        manufacturer="Kostal",
        model=coordinator.data[kostal.SettingsGeneral.INVERTER_MAKE],
        name=coordinator.data[kostal.SettingsGeneral.INVERTER_NAME],
        sw_version=coordinator.data[kostal.InfoVersions.VERSION_FW],
        hw_version=coordinator.data[kostal.InfoVersions.VERSION_HW],
    )

    async_add_entities(
        KostalPikoSensor(coordinator, description, device_info)
        for description in SENSOR_TYPES
    )


class KostalPikoSensor(CoordinatorEntity[PikoUpdateCoordinator], SensorEntity):
    """A Kostal Piko sensor updated using a DataUpdateCoordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PikoUpdateCoordinator,
        description: KostalPikoEntityDescription,
        deviceInfo: DeviceInfo,
    ) -> None:
        """Create a new KostalPikoSensor entity for inverter data."""
        super().__init__(coordinator)
        self.dxs_id = int(description.key)
        self.formatter = description.formatter
        self._attr_device_info = deviceInfo
        self._attr_unique_id = (
            f"{coordinator.data[kostal.InfoVersions.SERIAL_NUMBER]}_{description.key}"
        )
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.start_fetch_data(self.dxs_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.dxs_id)
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.dxs_id in self.coordinator.data
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is not None and self.dxs_id in self.coordinator.data:
            new_value = self.coordinator.data[self.dxs_id]
            if self.formatter is not None:
                self._attr_native_value = self.formatter(new_value)
            else:
                self._attr_native_value = new_value
            self.async_write_ha_state()
