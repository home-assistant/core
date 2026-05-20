"""Home Assistant integration module for Greencell EVSE sensor entities over MQTT."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase
from greencell_client.mqtt_parser import MqttParser
from greencell_client.utils import GreencellUtils

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
    MANUFACTURER,
)
from .models import GreencellConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
        value_fn=lambda data: data / 1000,
    ),
    GreencellSensorDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value_fn=lambda data: data / 1000,
    ),
    GreencellSensorDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value_fn=lambda data: data / 1000,
    ),
    GreencellSensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data,
    ),
    GreencellSensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data,
    ),
    GreencellSensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: data,
    ),
    GreencellSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: data,
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
        ],
        value_fn=lambda data: str(data).lower() if isinstance(data, str) else None,
    ),
)


# --- Config Flow Setup ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreencellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Greencell EVSE sensors from a config entry."""

    serial_number: str = entry.data[CONF_SERIAL_NUMBER]

    mqtt_topic_current = f"/greencell/evse/{serial_number}/current"
    mqtt_topic_voltage = f"/greencell/evse/{serial_number}/voltage"
    mqtt_topic_power = f"/greencell/evse/{serial_number}/power"
    mqtt_topic_status = f"/greencell/evse/{serial_number}/status"
    mqtt_topic_device_state = f"/greencell/evse/{serial_number}/device_state"

    desc_map = {desc.key: desc for desc in SENSOR_DESCRIPTIONS}

    runtime = entry.runtime_data
    access = runtime.access
    current_data_obj = runtime.current_data
    voltage_data_obj = runtime.voltage_data
    power_data_obj = runtime.power_data
    state_data_obj = runtime.state_data

    data_mapping = {
        "current": current_data_obj,
        "voltage": voltage_data_obj,
        "power": power_data_obj,
        "status": state_data_obj,
    }

    sensors: list[HabuSensor] = [
        Habu3PhaseSensor(
            sensor_data=data_mapping[description.key.split("_")[0]],
            phase=description.key.split("_")[-1],
            sensor_type=description.key,
            serial_number=serial_number,
            access=access,
            description=description,
        )
        for description in SENSOR_DESCRIPTIONS
        if description.key.startswith(("current_l", "voltage_l"))
    ]

    sensors.extend(
        HabuSingleSensor(
            sensor_data=data_mapping[key],
            serial_number=serial_number,
            sensor_type=key,
            access=access,
            description=desc_map[key],
        )
        for key in ("power", "status")
    )

    @callback
    def current_message_received(msg: ReceiveMessage) -> None:
        """Handle the current message."""
        MqttParser.parse_3phase_msg(msg.payload, current_data_obj)

    @callback
    def voltage_message_received(msg: ReceiveMessage) -> None:
        """Handle the voltage message."""
        MqttParser.parse_3phase_msg(msg.payload, voltage_data_obj)

    @callback
    def power_message_received(msg: ReceiveMessage) -> None:
        """Handle the power message."""
        MqttParser.parse_single_phase_msg(msg.payload, "momentary", power_data_obj)

    @callback
    def status_message_received(msg: ReceiveMessage) -> None:
        """Handle the status message. If the device is unavailable, disable the entity."""

        str_payload = (
            msg.payload.decode("utf-8", errors="ignore")
            if isinstance(msg.payload, (bytes, bytearray))
            else str(msg.payload)
        )

        if "UNAVAILABLE" in str_payload or "OFFLINE" in str_payload:
            access.update("UNAVAILABLE")
        else:
            MqttParser.parse_single_phase_msg(msg.payload, "state", state_data_obj)

    @callback
    def device_state_message_received(msg: ReceiveMessage) -> None:
        """Handle the device state message. If device was unavailable, enable the entity."""
        access.on_msg(msg.payload)

    try:
        for topic, handler in (
            (mqtt_topic_current, current_message_received),
            (mqtt_topic_voltage, voltage_message_received),
            (mqtt_topic_power, power_message_received),
            (mqtt_topic_status, status_message_received),
            (mqtt_topic_device_state, device_state_message_received),
        ):
            unsub = await mqtt.async_subscribe(hass, topic, handler)
            if unsub is not None:
                entry.async_on_unload(unsub)
    except HomeAssistantError as err:
        raise ConfigEntryNotReady(f"MQTT is unavailable: {err}") from err

    async_add_entities(sensors)


class HabuSensor(SensorEntity):
    """Abstract base class for Habu sensors integration."""

    entity_description: GreencellSensorDescription
    _attr_has_entity_name = True
    _remove_listener: Callable[[], None] | None = None

    def __init__(
        self,
        sensor_type: str,
        serial_number: str,
        access: GreencellAccess,
        description: GreencellSensorDescription,
    ) -> None:
        """Initialize the sensor entity."""
        self._sensor_type = sensor_type
        self._serial_number = serial_number
        self._access = access
        self.entity_description = description

        self._attr_unique_id = f"{serial_number}_{description.key}"

        if GreencellUtils.device_is_habu_den(self._serial_number):
            device_name = GREENCELL_HABU_DEN
        else:
            device_name = GREENCELL_OTHER_DEVICE

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"{device_name} {serial_number}",
            manufacturer=MANUFACTURER,
            model=device_name,
            serial_number=serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return not self._access.is_disabled()

    async def async_added_to_hass(self) -> None:
        """Register the entity with Home Assistant."""
        unsub = self._access.register_listener(self._schedule_update)
        if unsub is not None:
            self.async_on_remove(unsub)

    def _schedule_update(self) -> None:
        """Schedule an update for the entity."""
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
        """Initialize the 3-phase sensor."""
        super().__init__(sensor_type, serial_number, access, description)
        self._sensor_data = sensor_data
        self._phase = phase

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        raw_value = self._sensor_data.get_value(self._phase)
        if raw_value is None:
            return None
        return self.entity_description.value_fn(raw_value)


class HabuSingleSensor(HabuSensor):
    """Example class for sensors that return a single value."""

    def __init__(
        self,
        sensor_data: ElecDataSinglePhase,
        serial_number: str,
        sensor_type: str,
        access: GreencellAccess,
        description: GreencellSensorDescription,
    ) -> None:
        """Initialize the single-value sensor."""
        super().__init__(sensor_type, serial_number, access, description)
        self._value = sensor_data

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        raw_value = self._value.data
        if raw_value is None:
            return None
        return self.entity_description.value_fn(raw_value)
