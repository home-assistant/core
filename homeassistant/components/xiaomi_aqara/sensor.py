"""Support for Xiaomi Aqara sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import XiaomiDevice
from .const import BATTERY_MODELS, DOMAIN, GATEWAYS_KEY, POWER_MODELS

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "illumination": SensorEntityDescription(
        key="illumination",
        native_unit_of_measurement="lm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "lux": SensorEntityDescription(
        key="lux",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "bed_activity": SensorEntityDescription(
        key="bed_activity",
        native_unit_of_measurement="μm",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "load_power": SensorEntityDescription(
        key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "final_tilt_angle": SensorEntityDescription(
        key="final_tilt_angle",
    ),
    "coordination": SensorEntityDescription(
        key="coordination",
    ),
    "Battery": SensorEntityDescription(
        key="Battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Xiaomi devices."""
    entities: list[XiaomiSensor | XiaomiBatterySensor] = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for device in gateway.devices["sensor"]:
        if device["model"] == "sensor_ht":
            entities.append(
                XiaomiSensor(
                    device, "Temperature", "temperature", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(device, "Humidity", "humidity", gateway, config_entry)
            )
        elif device["model"] in ("weather", "weather.v1"):
            entities.append(
                XiaomiSensor(
                    device, "Temperature", "temperature", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(device, "Humidity", "humidity", gateway, config_entry)
            )
            entities.append(
                XiaomiSensor(device, "Pressure", "pressure", gateway, config_entry)
            )
        elif device["model"] == "sensor_motion.aq2":
            entities.append(
                XiaomiSensor(device, "Illumination", "lux", gateway, config_entry)
            )
        elif device["model"] in ("gateway", "gateway.v3", "acpartner.v3"):
            entities.append(
                XiaomiSensor(
                    device, "Illumination", "illumination", gateway, config_entry
                )
            )
        elif device["model"] in ("vibration",):
            entities.append(
                XiaomiSensor(
                    device, "Bed Activity", "bed_activity", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(
                    device, "Tilt Angle", "final_tilt_angle", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(
                    device, "Coordination", "coordination", gateway, config_entry
                )
            )
        else:
            _LOGGER.warning("Unmapped Device Model")

    # Set up battery sensors
    seen_sids = set()  # Set of device sids that are already seen
    for devices in gateway.devices.values():
        for device in devices:
            if device["sid"] in seen_sids:
                continue
            seen_sids.add(device["sid"])
            if device["model"] in BATTERY_MODELS:
                entities.append(
                    XiaomiBatterySensor(device, "Battery", gateway, config_entry)
                )
            if device["model"] in POWER_MODELS:
                entities.append(
                    XiaomiSensor(
                        device, "Load Power", "load_power", gateway, config_entry
                    )
                )
    async_add_entities(entities)


class XiaomiSensor(XiaomiDevice, SensorEntity):
    """Representation of a XiaomiSensor."""

    def __init__(self, device, name, data_key, xiaomi_hub, config_entry):
        """Initialize the XiaomiSensor."""
        self._data_key = data_key
        self.entity_description = SENSOR_TYPES[data_key]
        super().__init__(device, name, xiaomi_hub, config_entry)

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if (value := data.get(self._data_key)) is None:
            return False
        if self._data_key in ("coordination", "status"):
            self._attr_native_value = value
            return True
        value = float(value)
        if self._data_key in ("temperature", "humidity", "pressure"):
            value /= 100
        elif self._data_key in ("illumination",):
            value = max(value - 300, 0)
        if self._data_key == "temperature" and (value < -50 or value > 60):
            return False
        if self._data_key == "humidity" and (value <= 0 or value > 100):
            return False
        if self._data_key == "pressure" and value == 0:
            return False
        if self._data_key in ("illumination", "lux"):
            self._attr_native_value = round(value)
        else:
            self._attr_native_value = round(value, 1)
        return True


class XiaomiBatterySensor(XiaomiDevice, SensorEntity):
    """Representation of a XiaomiSensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        succeed = super().parse_voltage(data)
        if not succeed:
            return False
        battery_level = int(self._extra_state_attributes.pop(ATTR_BATTERY_LEVEL))
        if battery_level <= 0 or battery_level > 100:
            return False
        self._attr_native_value = battery_level
        return True

    def parse_voltage(self, data):
        """Parse battery level data sent by gateway."""
        return False  # Override parse_voltage to do nothing
