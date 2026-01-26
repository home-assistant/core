"""Home Assistant integration module for Greencell EVSE sensor entities over MQTT.

Provides:
- Sensor  classes:
  * HabuSensor: abstract base for all sensors with common device identification and availability logic.
  * Habu3PhaseSensor:  for per-phase sensors (current, voltage).
  * HabuSingleSensor:  single-value sensors (power, status).
- setup_sensors(): subscribes to MQTT topics for current, voltage, power, status, and device_state;
  updates sensor state objects and schedules Home Assistant state updates.
- async_setup_platform / async_setup_entry: legacy YAML and config-entry setup hooks.
"""

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase
from greencell_client.mqtt_parser import MqttParser
from greencell_client.utils import GreencellUtils

from homeassistant.components.mqtt import async_subscribe
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import DiscoveryInfoType, StateType

from .const import (
    GREENCELL_ACCESS_KEY,
    GREENCELL_CURRENT_DATA_KEY,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
    GREENCELL_POWER_DATA_KEY,
    GREENCELL_STATE_DATA_KEY,
    GREENCELL_VOLTAGE_DATA_KEY,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GreencellSensorDescription(SensorEntityDescription):
    """Describe a Greencell sensor."""

    value_fn: Callable[[Any], StateType]


SENSOR_DESCRIPTIONS = (
    GreencellSensorDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value_fn=lambda data: data / 1000 if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value_fn=lambda data: data / 1000 if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value_fn=lambda data: data / 1000 if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: data if data is not None else 0.0,
    ),
    GreencellSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "idle",
            "connected",
            "waiting_for_car",
            "charging",
            "finished",
            "error_car",
            "error_evse",
            "unknown",
        ],
        value_fn=lambda data: str(data).lower() if isinstance(data, str) else None,
    ),
)


# --- Config Flow Setup ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Greencell EVSE sensors from a config entry."""
    serial_number = entry.data.get("serial_number") if entry and entry.data else None
    if not serial_number:
        _LOGGER.error("Serial number not provided in ConfigEntry")
        return
    await setup_sensors(hass, serial_number, async_add_entities, entry)


class HabuSensor(SensorEntity, ABC):
    """Abstract base class for Habu sensors integration."""

    entity_description: GreencellSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        sensor_type: str,
        serial_number: str,
        access: GreencellAccess,
        description: GreencellSensorDescription,
    ) -> None:
        """Initialize the sensor entity.

        :param sensor_name: Name of the sensor displayed in Home Assistant
        :param unit: Unit of measurement (e.g. "A" or "V")
        :param sensor_type: Sensor type (e.g. "current", "voltage" or another for single sensors)
        :param serial_number: Serial number of the device
        """
        self._sensor_type = sensor_type
        self._serial_number = serial_number
        self._access = access
        self.entity_description = description
        self._access.register_listener(self._on_state_update)

    def _device_name(self) -> str:
        """Return the device name based on its type."""
        if GreencellUtils.device_is_habu_den(self._serial_number):
            return GREENCELL_HABU_DEN
        return GREENCELL_OTHER_DEVICE

    def _on_state_update(self) -> None:
        """Handle state update logic."""
        if self.hass:
            self.async_schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type and serial number."""
        return f"{self._device_name()}_{self._serial_number}_{self._sensor_type}_sensor"

    @property
    def device_info(self):
        """Return device information."""
        if GreencellUtils.device_is_habu_den(self._serial_number):
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


class Habu3PhaseSensor(HabuSensor):
    """Abstract class for 3-phase sensors (e.g. current, voltage)."""

    def __init__(
        self,
        sensor_data: ElecData3Phase,
        phase: str,
        sensor_type: str,
        serial_number: str,
        access: GreencellAccess,
        description: GreencellSensorDescription,
    ) -> None:
        """Initialize the 3-phase sensor.

        :param sensor_data: Object storing 3-phase data
        :param phase: Phase identifier ('l1', 'l2', 'l3')
        :param sensor_name: Name of the sensor displayed in Home Assistant
        :param unit: Unit of measurement
        :param sensor_type: Sensor type (e.g. "current" or "voltage")
        :param serial_number: Device serial number
        """
        super().__init__(sensor_type, serial_number, access, description)
        self._sensor_data = sensor_data
        self._phase = phase

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        raw_value = self._sensor_data.get_value(self._phase)
        if raw_value is None:
            return (
                "0.000"
                if self.entity_description.native_unit_of_measurement
                == UnitOfElectricCurrent.AMPERE
                else "0.00"
            )
        return self.entity_description.value_fn(raw_value)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type, phase, and serial number."""
        return f"{self._sensor_type}_sensor_{self._phase}_{self._serial_number}"


class HabuSingleSensor(HabuSensor):
    """Example class for sensors that return a single value."""

    def __init__(
        self,
        sensor_data,
        serial_number: str,
        sensor_type: str,
        access: GreencellAccess,
        description: GreencellSensorDescription,
    ) -> None:
        """Initialize the single-value sensor.

        :param sensor_data: Object storing single-phase data
        :param serial_number: Serial number of the device
        :param sensor_type: Sensor type (e.g. "power", "status")
        :param access: Greencell access level for the sensor
        :param description: Description of the sensor entity
        """
        super().__init__(sensor_type, serial_number, access, description)
        self._value = sensor_data

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._value is None:
            return (
                "0.0"
                if self.entity_description.native_unit_of_measurement
                == UnitOfPower.WATT
                else "UNKNOWN"
            )
        return self.entity_description.value_fn(self._value.data)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor based on type and serial number."""
        return f"{self._sensor_type}_sensor_{self._serial_number}"


# --- async_setup_platform function ---
async def setup_sensors(
    hass: HomeAssistant,
    serial_number: str,
    async_add_entities: AddConfigEntryEntitiesCallback | AddEntitiesCallback,
    entry: ConfigEntry | None = None,
):
    """Set up Greencell EVSE sensors based on serial number and config entry.

    :param hass: Home Assistant instance
    :param serial_number: Serial number of the Greencell EVSE device
    :param async_add_entities: Callback to add entities to Home Assistant
    :param entry: Optional config entry for the device
    """

    if entry is None:
        raise ValueError("Config entry is required for setup_sensors")

    mqtt_topic_current = f"/greencell/evse/{serial_number}/current"
    mqtt_topic_voltage = f"/greencell/evse/{serial_number}/voltage"
    mqtt_topic_power = f"/greencell/evse/{serial_number}/power"
    mqtt_topic_status = f"/greencell/evse/{serial_number}/status"
    mqtt_topic_device_state = f"/greencell/evse/{serial_number}/device_state"

    status_desc = next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == "status")
    power_desc = next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == "power")

    runtime = entry.runtime_data
    access = runtime[GREENCELL_ACCESS_KEY]
    current_data_obj = runtime[GREENCELL_CURRENT_DATA_KEY]
    voltage_data_obj = runtime[GREENCELL_VOLTAGE_DATA_KEY]
    power_data_obj = runtime[GREENCELL_POWER_DATA_KEY]
    state_data_obj = runtime[GREENCELL_STATE_DATA_KEY]

    current_sensors: list[Habu3PhaseSensor] = [
        Habu3PhaseSensor(
            current_data_obj,
            description.key.split("_")[-1],
            description.key,
            serial_number,
            access,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
        if description.key.startswith("current_l")
    ]

    voltage_sensors: list[Habu3PhaseSensor] = [
        Habu3PhaseSensor(
            voltage_data_obj,
            description.key.split("_")[-1],
            description.key,
            serial_number,
            access,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
        if description.key.startswith("voltage_l")
    ]

    state_sensor = HabuSingleSensor(
        state_data_obj,
        serial_number=serial_number,
        sensor_type="status",
        access=access,
        description=status_desc,
    )

    power_sensor = HabuSingleSensor(
        power_data_obj,
        serial_number=serial_number,
        sensor_type="power",
        access=access,
        description=power_desc,
    )

    @callback
    def current_message_received(msg) -> None:
        """Handle the current message."""
        MqttParser.parse_3phase_msg(msg.payload, current_data_obj)

    @callback
    def voltage_message_received(msg) -> None:
        """Handle the voltage message."""
        MqttParser.parse_3phase_msg(msg.payload, voltage_data_obj)

    @callback
    def power_message_received(msg) -> None:
        """Handle the power message."""
        MqttParser.parse_single_phase_msg(msg.payload, "momentary", power_data_obj)

    @callback
    def status_message_received(msg) -> None:
        """Handle the status message. If the device is unavailable, disable the entity."""
        try:
            str_payload = msg.payload.decode("utf-8", errors="ignore")
        except (AttributeError, TypeError):
            str_payload = str(msg.payload)

        if "UNAVAILABLE" in str_payload or "OFFLINE" in str_payload:
            access.update("UNAVAILABLE")
        else:
            MqttParser.parse_single_phase_msg(msg.payload, "state", state_data_obj)

    @callback
    def device_state_message_received(msg) -> None:
        """Handle the device state message. If device was unavailable, enable the entity."""
        access.on_msg(msg.payload)

    await async_subscribe(hass, mqtt_topic_current, current_message_received)
    await async_subscribe(hass, mqtt_topic_voltage, voltage_message_received)
    await async_subscribe(hass, mqtt_topic_power, power_message_received)
    await async_subscribe(hass, mqtt_topic_status, status_message_received)
    await async_subscribe(hass, mqtt_topic_device_state, device_state_message_received)

    async_add_entities(
        current_sensors + voltage_sensors + [state_sensor, power_sensor],
        update_before_add=True,
    )
