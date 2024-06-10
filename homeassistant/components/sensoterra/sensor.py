"""Sensoterra devices."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SensoterraCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up Sensoterra sensor."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Add %d probes", len(coordinator.data))

    sensors = [
        SensoterraEntity(coordinator, sensor.id)
        for probe in coordinator.data
        for sensor in probe.sensors()
        if sensor.type in ["MOISTURE", "TEMPERATURE"]
    ]

    # https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_sensor/
    #
    # Derive entity platforms from homeassistant.components.sensor.SensorEntity

    async_add_devices(sensors)


class SensoterraEntity(CoordinatorEntity, SensorEntity):
    """Sensoterra sensor like a soil moisture or temperature sensor.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available
    """

    def _get_probe(self):
        for probe in self.coordinator.data:
            for sensor in probe.sensors():
                if sensor.id == self._sensor_id:
                    return probe
        return None

    def _get_sensor(self):
        for probe in self.coordinator.data:
            for sensor in probe.sensors():
                if sensor.id == self._sensor_id:
                    return sensor
        return None

    def __init__(self, coordinator: SensoterraCoordinator, sensor_id: str) -> None:
        """Build a Sensoterra sensor like a soil moisture or temperature sensor."""

        super().__init__(coordinator, context=sensor_id)

        self._sensor_id = sensor_id
        sensor = self._get_sensor()
        probe = self._get_probe()

        # A unique_id for this entity within this domain.
        self._attr_unique_id = sensor.id

        if sensor.type == "MOISTURE":
            self._attr_device_class = SensorDeviceClass.MOISTURE
            if sensor.depth is None:
                self._attr_name = f"{probe.name} Soil moisture"
            else:
                self._attr_name = f"{probe.name} Soil moisture @ {sensor.depth} cm"
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor.type == "TEMPERATURE":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_name = f"{probe.name} Temperature"
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            # SensorDeviceClass.VOLTAGE
            # SensorDeviceClass.SIGNAL_STRENGTH
            assert sensor.type in ["MOISTURE", "TEMPERATURE"]

        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attrs_native_value = float
        self._attr_suggested_display_precision = 0
        if sensor.soil is not None:
            self._attr_extra_state_attributes = {
                "soil_type": sensor.soil,
            }
        self._attr_available = probe.state != "DISABLED"
        self._attr_native_value = sensor.value
        self._attr_force_update = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        sensor = self._get_sensor()
        self._attr_native_value = sensor.value
        self.async_write_ha_state()

    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        probe = self._get_probe()
        return {
            "identifiers": {(DOMAIN, probe.id)},
            "name": probe.name,
            "model": probe.sku,
            "manufacturer": "Sensoterra",
            "serial_number": probe.serial,
            "suggested_area": probe.location,  # area_id could also be set
            "configuration_url": "https://monitor.sensoterra.com",
        }
