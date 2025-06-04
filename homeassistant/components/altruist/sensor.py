"""Defines the Altruist sensor integration for Home Assistant.

Includes the setup of sensors, data update coordination, and sensor entity
implementation for interacting with Altruist devices.
"""

import logging
from typing import Any

from altruistclient import AltruistDeviceModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import AltruistConfigEntry
from .const import DOMAIN, SENSOR_DESCRIPTIONS
from .coordinator import AltruistDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AltruistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    client = config_entry.runtime_data
    coordinator = AltruistDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    sensors = [
        AltruistSensor(coordinator, client.device, SENSOR_DESCRIPTIONS[sensor_name])
        for sensor_name in client.sensor_names
    ]
    async_add_entities(sensors)


class AltruistSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a LuftdatenSensor sensor."""

    _native_value: Any
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: AltruistDeviceModel,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the LuftdatenSensor sensor."""
        super().__init__(coordinator)
        self._device = device
        self._device_id = device.id
        self._native_value = None
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"altruist_{self._device_id}-{self.entity_description.key}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        name = self.entity_description.name
        return name if isinstance(name, str) else ""

    @property
    def native_value(self) -> float | int:
        """Return the value reported by the sensor."""
        return self._native_value

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        if self.device_class in [SensorDeviceClass.PM1, SensorDeviceClass.PM25]:
            return "mdi:thought-bubble-outline"
        if self.device_class == SensorDeviceClass.PM10:
            return "mdi:thought-bubble"

        return ""

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Altruist Sensor {self._device_id}",
            manufacturer="Robonomics",
            model="Altruist Sensor",
            sw_version=self._device.fw_version,
            configuration_url=f"http://{self._device.ip_address}",
            serial_number=self._device_id,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for sensordata_type in self.coordinator.data:
            if sensordata_type == self.entity_description.key:
                self._native_value = (
                    round(float(self.coordinator.data[sensordata_type]), 2)
                    if "." in self.coordinator.data[sensordata_type]
                    else int(self.coordinator.data[sensordata_type])
                )
        self.async_write_ha_state()
