"""sensors.py

Home Assistant integration module for Greencell EVSE sensor entities over MQTT.

Provides:
- Data storage classes:
  * Habu3PhaseSensorData: tracks three-phase values (l1, l2, l3).
  * HabuSingleSensorData: stores single-value metrics (power, status).
- Sensor base classes:
  * HabuSensor: abstract base for all sensors with common device identification and availability logic.
  * Habu3PhaseSensor: abstract for per-phase sensors (current, voltage).
  * HabuSingleSensor: abstract for single-value sensors (power, status).
- Concrete sensor implementations:
  * HabuCurrentSensor: converts mA→A with three decimals.
  * HabuVoltageSensor: formats voltage with two decimals.
  * HabuPowerSensor: formats power with one decimal.
  * HabuStatusSensor: reports raw status strings.
- setup_sensors(): subscribes to MQTT topics for current, voltage, power, status, and device_state;
  updates sensor state objects and schedules Home Assistant state updates.
- async_setup_platform / async_setup_entry: legacy YAML and config-entry setup hooks.
"""

from abc import ABC, abstractmethod
import json
from json import JSONDecodeError
import logging

from homeassistant.components.mqtt import async_subscribe
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    GREENCELL_HABU_DEN,
    GREENCELL_HABU_DEN_SERIAL_PREFIX,
    GREENCELL_OTHER_DEVICE,
    MANUFACTURER,
    GreencellHaAccessLevelEnum as AccessLevel,
)
from .helper import GreencellAccess

_LOGGER = logging.getLogger(__name__)


class Habu3PhaseSensorData:
    """Class storing sensor data (e.g. current or voltage) for 3 phases."""

    def __init__(self) -> None:
        self._data = {"l1": None, "l2": None, "l3": None}

    @property
    def data(self) -> dict:
        """Return the internal data dictionary."""
        return self._data

    def update_data(self, new_data: dict) -> None:
        """Update sensor data if the dictionary contains keys corresponding to the phases."""
        for phase in ["l1", "l2", "l3"]:
            if phase in new_data:
                self._data[phase] = new_data[phase]


class HabuSingleSensorData:
    """Class storing single-value data like power, etc."""

    def __init__(self) -> None:
        self._data = None

    @property
    def data(self) -> float:
        """Return the internal data."""
        return self._data

    def update_data(self, new_data) -> None:
        """Update sensor data"""
        self._data = new_data


class HabuSensor(SensorEntity, ABC):
    """Abstract base class for Habu sensors integration."""

    def __init__(
        self,
        sensor_name: str,
        unit: str,
        sensor_type: str,
        serial_number: str,
        access: GreencellAccess,
    ) -> None:
        """:param sensor_name: Name of the sensor displayed in Home Assistant
        :param unit: Unit of measurement (e.g. "A" or "V")
        :param sensor_type: Sensor type (e.g. "current", "voltage" or another for single sensors)
        :param serial_number: Serial number of the device
        """
        self._attr_name = sensor_name
        self._unit = unit
        self._sensor_type = sensor_type
        self._serial_number = serial_number
        self._access = access

    def _device_is_habu_den(self) -> bool:
        """Check if the device is a Habu Den based on its serial number."""
        return self._serial_number.startswith(GREENCELL_HABU_DEN_SERIAL_PREFIX)

    def _device_name(self) -> str:
        """Return the device name based on its type."""
        if self._device_is_habu_den():
            return GREENCELL_HABU_DEN
        return GREENCELL_OTHER_DEVICE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type and serial number."""
        return f"{self._device_name()}_{self._serial_number}_{self._sensor_type}_sensor"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @abstractmethod
    def convert_value(self, raw_value) -> str:
        """Convert the raw value to a format suitable for display.
        Must be implemented in derived classes.
        """

    def update(self) -> None:
        """Update method - updates are handled externally (e.g. via MQTT callbacks)."""

    @property
    def device_info(self) -> dict:
        """Return device information."""
        if self._device_is_habu_den():
            device_name = GREENCELL_HABU_DEN
        else:
            device_name = GREENCELL_OTHER_DEVICE
        return {
            "identifiers": {(self._serial_number,)},
            "name": f"{device_name} {self._serial_number}",
            "manufacturer": MANUFACTURER,
            "model": device_name,
        }

    @property
    @abstractmethod
    def icon(self) -> str:
        """Return the icon for the sensor.
        Must be implemented in derived classes.
        """

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return not self._access.is_disabled()

    async def async_added_to_hass(self) -> None:
        """Register the entity with Home Assistant."""
        self._access.register_listener(self._schedule_update)

    def _schedule_update(self) -> None:
        """Schedule an update for the entity."""
        if self.hass:
            self.async_schedule_update_ha_state()


class Habu3PhaseSensor(HabuSensor, ABC):
    """Abstract class for 3-phase sensors (e.g. current, voltage)."""

    def __init__(
        self,
        sensor_data: Habu3PhaseSensorData,
        phase: str,
        sensor_name: str,
        unit: str,
        sensor_type: str,
        serial_number: str,
        access: GreencellAccess,
    ) -> None:
        """:param sensor_data: Object storing 3-phase data
        :param phase: Phase identifier ('l1', 'l2', 'l3')
        :param sensor_name: Name of the sensor displayed in Home Assistant
        :param unit: Unit of measurement
        :param sensor_type: Sensor type (e.g. "current" or "voltage")
        :param serial_number: Device serial number
        """
        super().__init__(sensor_name, unit, sensor_type, serial_number, access)
        self._sensor_data = sensor_data.data
        self._phase = phase

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        raw_value = self._sensor_data.get(self._phase)
        if raw_value is None:
            return None
        return self.convert_value(raw_value)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type, phase, and serial number."""
        return f"{self._sensor_type}_sensor_{self._phase}_{self._serial_number}"


class HabuCurrentSensor(Habu3PhaseSensor):
    def __init__(
        self,
        sensor_data: Habu3PhaseSensorData,
        phase: str,
        sensor_name: str,
        serial_number: str,
        access: GreencellAccess,
        unit: str = "A",
    ) -> None:
        super().__init__(
            sensor_data,
            phase,
            sensor_name,
            unit,
            sensor_type="current",
            serial_number=serial_number,
            access=access,
        )

    def convert_value(self, value) -> str:
        """Convert the raw current value in mA to a string in A with 3 decimal places."""
        try:
            numeric = float(value)
            return f"{numeric / 1000:.3f}"
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Cannot convert current: %s", ex)
            return str(value)

    @property
    def icon(self) -> str:
        """Return the icon for the current sensor."""
        return "mdi:flash-auto"


class HabuVoltageSensor(Habu3PhaseSensor):
    def __init__(
        self,
        sensor_data: Habu3PhaseSensorData,
        phase: str,
        sensor_name: str,
        serial_number: str,
        access: GreencellAccess,
        unit: str = "V",
    ) -> None:
        super().__init__(
            sensor_data,
            phase,
            sensor_name,
            unit,
            sensor_type="voltage",
            serial_number=serial_number,
            access=access,
        )

    def convert_value(self, value) -> str:
        """Convert the raw voltage value to a string in V with 2 decimal places."""
        try:
            numeric = float(value)
            return f"{numeric:.2f}"
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Cannot convert voltage: %s", ex)
            return str(value)

    @property
    def icon(self) -> str:
        """Return the icon for the voltage sensor."""
        return "mdi:meter-electric"


class HabuSingleSensor(HabuSensor):
    """Example class for sensors that return a single value."""

    def __init__(
        self,
        raw_value,
        sensor_name: str,
        serial_number: str,
        unit: str,
        sensor_type: str,
        access: GreencellAccess,
    ) -> None:
        super().__init__(sensor_name, unit, sensor_type, serial_number, access)
        self._value = raw_value

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if self._value is None:
            return None
        return self.convert_value(self._value)

    def update_value(self, new_value) -> None:
        """Update the stored value."""
        self._value = new_value

    @abstractmethod
    def convert_value(self, raw_value) -> str:
        """Concrete class should convert the raw value."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type and serial number."""
        return f"{self._sensor_type}_sensor_{self._serial_number}"


class HabuPowerSensor(HabuSingleSensor):
    def __init__(
        self,
        raw_value,
        sensor_name: str,
        serial_number: str,
        access: GreencellAccess,
        unit: str = "W",
    ) -> None:
        super().__init__(
            raw_value,
            sensor_name,
            serial_number,
            unit,
            sensor_type="power",
            access=access,
        )

    def convert_value(self, raw_value) -> str:
        """Convert the raw power value to a string in W with 1 decimal place."""
        if raw_value.data is None:
            return "0.0"
        try:
            numeric = float(raw_value.data)
            return f"{numeric:.1f}"
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.error("Cannot convert power: %s", ex)
            return "0.0"

    @property
    def icon(self) -> str:
        """Return the icon for the power sensor."""
        return "mdi:battery-charging-high"


class HabuStatusSensor(HabuSingleSensor):
    def __init__(
        self,
        raw_value,
        sensor_name: str,
        serial_number: str,
        access: GreencellAccess,
        unit: str = "",
    ) -> None:
        super().__init__(
            raw_value,
            sensor_name,
            serial_number,
            unit,
            sensor_type="status",
            access=access,
        )

    def convert_value(self, raw_value) -> str:
        """Convert the raw status value to a string."""
        try:
            return str(raw_value.data)
        except (AttributeError, TypeError) as ex:
            _LOGGER.error("Cannot convert status: %s", ex)
            return "UNKNOWN"

    @property
    def icon(self) -> str:
        """Return the icon for the status sensor."""
        return "mdi:ev-plug-type2"


# --- async_setup_platform function ---
async def setup_sensors(
    hass: HomeAssistant, serial_number: str, async_add_entities: AddEntitiesCallback
):
    """Set up the Greencell EVSE sensors."""
    mqtt_topic_current = f"/greencell/evse/{serial_number}/current"
    mqtt_topic_voltage = f"/greencell/evse/{serial_number}/voltage"
    mqtt_topic_power = f"/greencell/evse/{serial_number}/power"
    mqtt_topic_status = f"/greencell/evse/{serial_number}/status"
    mqtt_topic_device_state = f"/greencell/evse/{serial_number}/device_state"

    access = GreencellAccess(AccessLevel.EXECUTE)
    current_data_obj = Habu3PhaseSensorData()
    voltage_data_obj = Habu3PhaseSensorData()
    power_data_obj = HabuSingleSensorData()
    state_data_obj = HabuSingleSensorData()

    current_sensors = [
        HabuCurrentSensor(
            current_data_obj,
            phase="l1",
            sensor_name="Current phase L1",
            serial_number=serial_number,
            access=access,
        ),
        HabuCurrentSensor(
            current_data_obj,
            phase="l2",
            sensor_name="Current phase L2",
            serial_number=serial_number,
            access=access,
        ),
        HabuCurrentSensor(
            current_data_obj,
            phase="l3",
            sensor_name="Current phase L3",
            serial_number=serial_number,
            access=access,
        ),
    ]

    voltage_sensors = [
        HabuVoltageSensor(
            voltage_data_obj,
            phase="l1",
            sensor_name="Voltage phase L1",
            serial_number=serial_number,
            access=access,
        ),
        HabuVoltageSensor(
            voltage_data_obj,
            phase="l2",
            sensor_name="Voltage phase L2",
            serial_number=serial_number,
            access=access,
        ),
        HabuVoltageSensor(
            voltage_data_obj,
            phase="l3",
            sensor_name="Voltage phase L3",
            serial_number=serial_number,
            access=access,
        ),
    ]

    power_sensor = HabuPowerSensor(
        power_data_obj,
        sensor_name="Charging Power",
        serial_number=serial_number,
        access=access,
    )
    state_sensor = HabuStatusSensor(
        state_data_obj,
        sensor_name="EVSE state",
        serial_number=serial_number,
        access=access,
    )

    @callback
    def current_message_received(msg) -> None:
        """Handle the current message."""
        try:
            data = json.loads(msg.payload)
        except JSONDecodeError as ex:
            _LOGGER.error("Invalid JSON payload for current data: %s", ex)
            return

        try:
            current_data_obj.update_data(data)
        except (KeyError, TypeError, ValueError) as ex:
            _LOGGER.error("Error updating current data object: %s", ex)
            return

        for sensor in current_sensors:
            try:
                sensor.async_schedule_update_ha_state(True)
            except AttributeError as ex:
                _LOGGER.error("Error scheduling update for sensor: %s", ex)

    @callback
    def voltage_message_received(msg) -> None:
        """Handle the voltage message."""
        try:
            data = json.loads(msg.payload)
        except JSONDecodeError as ex:
            _LOGGER.error("Invalid JSON payload for voltage data: %s", ex)
            return

        try:
            voltage_data_obj.update_data(data)
        except (KeyError, TypeError, ValueError) as ex:
            _LOGGER.error("Error updating voltage data object: %s", ex)
            return

        for sensor in voltage_sensors:
            try:
                sensor.async_schedule_update_ha_state(True)
            except AttributeError as ex:
                _LOGGER.error("Error scheduling update for sensor: %s", ex)

    @callback
    def power_message_received(msg) -> None:
        """Handle the power message."""
        try:
            data = json.loads(msg.payload)
        except JSONDecodeError as ex:
            _LOGGER.error("Invalid JSON payload for power data: %s", ex)
            return

        momentary = data.get("momentary")
        try:
            power_data_obj.update_data(momentary)
        except (KeyError, TypeError, ValueError) as ex:
            _LOGGER.error("Error updating power data object: %s", ex)
            return

        try:
            power_sensor.async_schedule_update_ha_state(True)
        except AttributeError as ex:
            _LOGGER.error("Error scheduling update for power sensor: %s", ex)

    @callback
    def status_message_received(msg) -> None:
        """Handle the status message. If the device is offline, disable the entity."""

        try:
            data = json.loads(msg.payload)
        except JSONDecodeError as ex:
            _LOGGER.error("Invalid JSON payload for status data: %s", ex)
            return

        state = data.get("state")
        if not isinstance(state, str):
            _LOGGER.error("State value is not a string: %s", state)
            return

        if "OFFLINE" in state:
            access.update("OFFLINE")

        try:
            state_data_obj.update_data(state)
        except (KeyError, TypeError, ValueError) as ex:
            _LOGGER.error("Error updating state data object: %s", ex)
            return

        try:
            state_sensor.async_schedule_update_ha_state(True)
        except AttributeError as ex:
            _LOGGER.error("Error scheduling update for state sensor: %s", ex)

    @callback
    def device_state_message_received(msg) -> None:
        """Handle the device state message. If device was offline, enable the entity."""
        try:
            data = json.loads(msg.payload)
        except JSONDecodeError as ex:
            _LOGGER.error("Invalid JSON payload for device state data: %s", ex)
            return

        level = data.get("level")
        if level is not None:
            try:
                access.update(level)
            except (TypeError, ValueError, KeyError) as ex:
                _LOGGER.error("Error updating access level: %s", ex)

    await async_subscribe(hass, mqtt_topic_current, current_message_received)
    await async_subscribe(hass, mqtt_topic_voltage, voltage_message_received)
    await async_subscribe(hass, mqtt_topic_power, power_message_received)
    await async_subscribe(hass, mqtt_topic_status, status_message_received)
    await async_subscribe(hass, mqtt_topic_device_state, device_state_message_received)

    async_add_entities(
        current_sensors + voltage_sensors + [power_sensor, state_sensor],
        update_before_add=True,
    )


# --- YAML Setup ---
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Greencell EVSE sensors from YAML configuration."""
    serial_number = config.get("serial_number") if config else None
    if not serial_number:
        _LOGGER.error("Serial number not provided in YAML config.")
        return
    await setup_sensors(hass, serial_number, async_add_entities)


# --- Config Flow Setup ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Greencell EVSE sensors from a config entry."""
    serial_number = entry.data.get("serial_number") if entry and entry.data else None
    if not serial_number:
        _LOGGER.error("Serial number not provided in ConfigEntry.")
        return
    await setup_sensors(hass, serial_number, async_add_entities)
