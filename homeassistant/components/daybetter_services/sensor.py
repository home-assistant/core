"""Support for DayBetter sensors."""

from __future__ import annotations

import logging
from typing import Any
import uuid

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DayBetter sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    devices = data["devices"]

    # Ensure devices is a list, even if it's None
    if devices is None:
        devices = []

    _LOGGER.debug("Original devices list: %s", devices)

    # Remove duplicate devices based on deviceId and deviceName
    unique_devices = []
    seen_devices = set()

    for dev in devices:
        # Create a unique key based on deviceId and deviceName
        device_id = dev.get("deviceId")
        device_name = dev.get("deviceName")
        unique_key = (device_id, device_name)

        _LOGGER.debug("Processing device: %s (ID: %s)", device_name, device_id)

        # Only add device if we haven't seen this combination before
        if unique_key not in seen_devices:
            seen_devices.add(unique_key)
            unique_devices.append(dev)
            _LOGGER.debug("Added device: %s (ID: %s)", device_name, device_id)
        else:
            _LOGGER.debug(
                "Skipping duplicate device: %s (ID: %s)", device_name, device_id
            )

    _LOGGER.debug("Unique devices list: %s", unique_devices)

    # Get sensor PIDs list
    pids_data = await api.fetch_pids()
    sensor_pids_str = pids_data.get("sensor", "")
    sensor_pids = set(sensor_pids_str.split(",")) if sensor_pids_str else set()

    _LOGGER.debug("Sensor PIDs string: %s", sensor_pids_str)
    _LOGGER.debug("Sensor PIDs set: %s", sensor_pids)

    # Check if each device's deviceMoldPid is in sensor_pids
    for dev in unique_devices:
        device_name = dev.get("deviceName", "unknown")
        device_mold_pid = dev.get("deviceMoldPid", "")
        is_sensor = device_mold_pid in sensor_pids
        _LOGGER.debug(
            "Device %s (PID: %s) is sensor: %s", device_name, device_mold_pid, is_sensor
        )

    # Create separate temperature and humidity sensor entities for sensor devices
    sensors = []
    for dev in unique_devices:
        if dev.get("deviceMoldPid") in sensor_pids:
            device_name = dev.get("deviceName", "unknown")
            device_group_name = dev.get("deviceGroupName", "DayBetter Sensor")

            # Create temperature sensor
            temp_sensor = DayBetterTemperatureSensor(
                hass, api, dev, data.get("mqtt_manager")
            )
            sensors.append(temp_sensor)

            # Create humidity sensor
            humidity_sensor = DayBetterHumiditySensor(
                hass, api, dev, data.get("mqtt_manager")
            )
            sensors.append(humidity_sensor)

    _LOGGER.info("Created %d sensor entities", len(sensors))
    async_add_entities(sensors)


class DayBetterTemperatureSensor(SensorEntity):
    """Representation of a DayBetter temperature sensor."""

    def __init__(
        self, hass: HomeAssistant, api, device: dict[str, Any], mqtt_manager
    ) -> None:
        """Initialize the temperature sensor."""
        self.hass = hass
        self._api = api
        self._device = device
        self._mqtt_manager = mqtt_manager
        self._device_name = device.get("deviceName", "unknown")
        self._device_group_name = device.get("deviceGroupName", "DayBetter Sensor")

        # Set sensor attributes
        self._attr_name = f"{self._device_group_name} Temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Initialize temperature value (convert from Celsius to Fahrenheit)
        celsius_temp = device.get("temperature", 20.0)
        self._attr_native_value = self._celsius_to_fahrenheit(celsius_temp)

        # Generate unique ID
        device_id = device.get("id", "")
        device_mac = device.get("mac", "")
        device_group_id = device.get("deviceGroupId", "")
        device_mold_pid = device.get("deviceMoldPid", "")

        identifiers = [
            self._device_name,
            device_id,
            device_mac,
            device_group_id,
            device_mold_pid,
        ]
        unique_part = "_".join([str(ident) for ident in identifiers if ident])

        if not unique_part:
            unique_part = f"{self._device_name}_{uuid.uuid4().hex[:8]}"

        self._attr_unique_id = f"daybetter_temp_{unique_part}"

    def _celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return (celsius * 9 / 5) + 32

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Register for MQTT updates if MQTT manager exists
        if self._mqtt_manager:
            # Register sensor data callback, using device name + sensor type as unique key
            message_handler = self._mqtt_manager.get_message_handler()
            message_handler.register_sensor_data_callback(
                self._handle_sensor_data_update, f"{self._device_name}_temperature"
            )

            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"daybetter_sensor_update_{self._device_name}",
                    self._handle_mqtt_update,
                )
            )

    @callback
    def _handle_sensor_data_update(
        self,
        device_name: str,
        sensor_type: str,
        value: float,
        device_type: int,
        topic: str,
    ) -> None:
        """Handle sensor data updates from MQTT."""
        _LOGGER.info(
            "🔄 Temperature sensor callback called: %s, current device: %s, type: %s, value: %s",
            device_name,
            self._device_name,
            sensor_type,
            value,
        )
        if device_name == self._device_name and sensor_type == "temperature":
            # Convert Celsius to Fahrenheit (MQTT sends Celsius)
            fahrenheit_value = self._celsius_to_fahrenheit(value)
            _LOGGER.info(
                "✅ Temperature device name matches, updating temperature: %s°F -> %s°F (from %s°C)",
                self._attr_native_value,
                fahrenheit_value,
                value,
            )
            self._attr_native_value = fahrenheit_value
            _LOGGER.info("🔄 Temperature calling async_write_ha_state()")
            self.async_write_ha_state()
            _LOGGER.info("✅ Temperature async_write_ha_state() call completed")
        else:
            _LOGGER.debug(
                "Temperature device name or type doesn't match, skipping update: %s != %s, %s != temperature",
                device_name,
                self._device_name,
                sensor_type,
            )

    @callback
    def _handle_mqtt_update(self, state: dict) -> None:
        """Handle MQTT state updates."""
        _LOGGER.debug(
            "Received MQTT update for temperature sensor %s: %s",
            self._device_name,
            state,
        )

        # Update temperature value based on MQTT message (convert from Celsius to Fahrenheit)
        if "temperature" in state:
            celsius_temp = float(state["temperature"])
            fahrenheit_temp = self._celsius_to_fahrenheit(celsius_temp)
            _LOGGER.debug(
                "Converting temperature from %s°C to %s°F",
                celsius_temp,
                fahrenheit_temp,
            )
            self._attr_native_value = fahrenheit_temp

        # Update HA state
        self.async_write_ha_state()


class DayBetterHumiditySensor(SensorEntity):
    """Representation of a DayBetter humidity sensor."""

    def __init__(
        self, hass: HomeAssistant, api, device: dict[str, Any], mqtt_manager
    ) -> None:
        """Initialize the humidity sensor."""
        self.hass = hass
        self._api = api
        self._device = device
        self._mqtt_manager = mqtt_manager
        self._device_name = device.get("deviceName", "unknown")
        self._device_group_name = device.get("deviceGroupName", "DayBetter Sensor")

        # Set sensor attributes
        self._attr_name = f"{self._device_group_name} Humidity"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Initialize humidity value
        self._attr_native_value = device.get("humidity", 50.0)

        # Generate unique ID
        device_id = device.get("id", "")
        device_mac = device.get("mac", "")
        device_group_id = device.get("deviceGroupId", "")
        device_mold_pid = device.get("deviceMoldPid", "")

        identifiers = [
            self._device_name,
            device_id,
            device_mac,
            device_group_id,
            device_mold_pid,
        ]
        unique_part = "_".join([str(ident) for ident in identifiers if ident])

        if not unique_part:
            unique_part = f"{self._device_name}_{uuid.uuid4().hex[:8]}"

        self._attr_unique_id = f"daybetter_humidity_{unique_part}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Register for MQTT updates if MQTT manager exists
        if self._mqtt_manager:
            # Register sensor data callback, using device name + sensor type as unique key
            message_handler = self._mqtt_manager.get_message_handler()
            message_handler.register_sensor_data_callback(
                self._handle_sensor_data_update, f"{self._device_name}_humidity"
            )

            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"daybetter_sensor_update_{self._device_name}",
                    self._handle_mqtt_update,
                )
            )

    @callback
    def _handle_sensor_data_update(
        self,
        device_name: str,
        sensor_type: str,
        value: float,
        device_type: int,
        topic: str,
    ) -> None:
        """Handle sensor data updates from MQTT."""
        _LOGGER.info(
            "🔄 Humidity sensor callback called: %s, current device: %s, type: %s, value: %s",
            device_name,
            self._device_name,
            sensor_type,
            value,
        )
        if device_name == self._device_name and sensor_type == "humidity":
            _LOGGER.info(
                "✅ Humidity device name matches, updating humidity: %s -> %s",
                self._attr_native_value,
                value,
            )
            self._attr_native_value = value
            _LOGGER.info("🔄 Humidity calling async_write_ha_state()")
            self.async_write_ha_state()
            _LOGGER.info("✅ Humidity async_write_ha_state() call completed")
        else:
            _LOGGER.debug(
                "Humidity device name or type doesn't match, skipping update: %s != %s, %s != humidity",
                device_name,
                self._device_name,
                sensor_type,
            )

    @callback
    def _handle_mqtt_update(self, state: dict) -> None:
        """Handle MQTT state updates."""
        _LOGGER.debug(
            "Received MQTT update for humidity sensor %s: %s", self._device_name, state
        )

        # Update humidity value based on MQTT message
        if "humidity" in state:
            self._attr_native_value = float(state["humidity"])

        # Update HA state
        self.async_write_ha_state()
