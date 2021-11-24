"""Support for Tuya sensors."""
from __future__ import annotations

from typing import cast

from tuya_iot import TuyaDevice, TuyaDeviceManager
from tuya_iot.device import TuyaDeviceStatusRange

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PM1,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    DEVICE_CLASS_VOLTAGE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_TUYA_STATUS,
    DEVICE_CLASS_UNITS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
    UnitOfMeasurement,
)

# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=DPCode.BATTERY_PERCENTAGE,
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=DPCode.BATTERY_STATE,
        name="Battery State",
        icon="mdi:battery",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=DPCode.BATTERY_VALUE,
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=DPCode.VA_BATTERY,
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[SensorEntityDescription, ...]] = {
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Current Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT_F,
            name="Current Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.STATUS,
            name="Status",
            device_class=DEVICE_CLASS_TUYA_STATUS,
        ),
    ),
    # CO2 Detector
    # https://developer.tuya.com/en/docs/iot/categoryco2bj?id=Kaiuz3wes7yuy
    "co2bj": (
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # CO Detector
    # https://developer.tuya.com/en/docs/iot/categorycobj?id=Kaiuz3u1j6q1v
    "cobj": (
        SensorEntityDescription(
            key=DPCode.CO_VALUE,
            name="Carbon Monoxide",
            device_class=DEVICE_CLASS_CO,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Air Quality Monitor
    # No specification on Tuya portal
    "hjjcy": (
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            name="Formaldehyde",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VOC_VALUE,
            name="Volatile Organic Compound",
            device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.PM25_VALUE,
            name="Particulate Matter 2.5 µm",
            device_class=DEVICE_CLASS_PM25,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            name="Current",
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key=DPCode.CUR_POWER,
            name="Power",
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            name="Voltage",
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    # Formaldehyde Detector
    # Note: Not documented
    "jqbj": (
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VOC_VALUE,
            name="Volatile Organic Compound",
            device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.PM25_VALUE,
            name="Particulate Matter 2.5 µm",
            device_class=DEVICE_CLASS_PM25,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            name="Formaldehyde",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Methane Detector
    # https://developer.tuya.com/en/docs/iot/categoryjwbj?id=Kaiuz40u98lkm
    "jwbj": (
        SensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            name="Methane",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Luminance Sensor
    # https://developer.tuya.com/en/docs/iot/categoryldcg?id=Kaiuz3n7u69l8
    "ldcg": (
        SensorEntityDescription(
            key=DPCode.BRIGHT_STATE,
            name="Luminosity",
            icon="mdi:brightness-6",
        ),
        SensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            name="Luminosity",
            device_class=DEVICE_CLASS_ILLUMINANCE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Door Window Sensor
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m
    "mcs": BATTERY_SENSORS,
    # PIR Detector
    # https://developer.tuya.com/en/docs/iot/categorypir?id=Kaiuz3ss11b80
    "pir": BATTERY_SENSORS,
    # PM2.5 Sensor
    # https://developer.tuya.com/en/docs/iot/categorypm25?id=Kaiuz3qof3yfu
    "pm2.5": (
        SensorEntityDescription(
            key=DPCode.PM25_VALUE,
            name="Particulate Matter 2.5 µm",
            device_class=DEVICE_CLASS_PM25,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            name="Formaldehyde",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VOC_VALUE,
            name="Volatile Organic Compound",
            device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.PM1,
            name="Particulate Matter 1.0 µm",
            device_class=DEVICE_CLASS_PM1,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.PM10,
            name="Particulate Matter 10.0 µm",
            device_class=DEVICE_CLASS_PM10,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SensorEntityDescription(
            key=DPCode.WORK_POWER,
            name="Power",
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    # Gas Detector
    # https://developer.tuya.com/en/docs/iot/categoryrqbj?id=Kaiuz3d162ubw
    "rqbj": (
        SensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            icon="mdi:gas-cylinder",
            device_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Water Detector
    # https://developer.tuya.com/en/docs/iot/categorysj?id=Kaiuz3iub2sli
    "sj": BATTERY_SENSORS,
    # Emergency Button
    # https://developer.tuya.com/en/docs/iot/categorysos?id=Kaiuz3oi6agjy
    "sos": BATTERY_SENSORS,
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SensorEntityDescription(
            key=DPCode.SENSOR_TEMPERATURE,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.SENSOR_HUMIDITY,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.WIRELESS_ELECTRICITY,
            name="Battery",
            device_class=DEVICE_CLASS_BATTERY,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": BATTERY_SENSORS,
    # Volatile Organic Compound Sensor
    # Note: Undocumented in cloud API docs, based on test device
    "voc": (
        SensorEntityDescription(
            key=DPCode.CO2_VALUE,
            name="Carbon Dioxide",
            device_class=DEVICE_CLASS_CO2,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.PM25_VALUE,
            name="Particulate Matter 2.5 µm",
            device_class=DEVICE_CLASS_PM25,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            name="Formaldehyde",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VOC_VALUE,
            name="Volatile Organic Compound",
            device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Temperature and Humidity Sensor
    # https://developer.tuya.com/en/docs/iot/categorywsdcg?id=Kaiuz3hinij34
    "wsdcg": (
        SensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            name="Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            name="Humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            name="Luminosity",
            device_class=DEVICE_CLASS_ILLUMINANCE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Pressure Sensor
    # https://developer.tuya.com/en/docs/iot/categoryylcg?id=Kaiuz3kc2e4gm
    "ylcg": (
        SensorEntityDescription(
            key=DPCode.PRESSURE_VALUE,
            device_class=DEVICE_CLASS_PRESSURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Smoke Detector
    # https://developer.tuya.com/en/docs/iot/categoryywbj?id=Kaiuz3f6sf952
    "ywbj": (
        SensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            name="Smoke Amount",
            icon="mdi:smoke-detector",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            device_class=STATE_CLASS_MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": BATTERY_SENSORS,
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["pc"] = SENSORS["kg"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := SENSORS.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaSensorEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSensorEntity(TuyaEntity, SensorEntity):
    """Tuya Sensor Entity."""

    _status_range: TuyaDeviceStatusRange | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: SensorEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if status_range := device.status_range.get(description.key):
            self._status_range = cast(TuyaDeviceStatusRange, status_range)

            # Extract type data from integer status range,
            # and determine unit of measurement
            if self._status_range.type == "Integer":
                self._type_data = IntegerTypeData.from_json(self._status_range.values)
                if description.native_unit_of_measurement is None:
                    self._attr_native_unit_of_measurement = self._type_data.unit

            # Extract type data from enum status range
            elif self._status_range.type == "Enum":
                self._type_data = EnumTypeData.from_json(self._status_range.values)

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.unit_of_measurement) or uoms.get(
                self.unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # Unknown or unsupported data type
        if self._status_range is None or self._status_range.type not in (
            "Integer",
            "String",
            "Enum",
        ):
            return None

        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None:
            return None

        # Scale integer/float value
        if isinstance(self._type_data, IntegerTypeData):
            scaled_value = self._type_data.scale_value(value)
            if self._uom and self._uom.conversion_fn is not None:
                return self._uom.conversion_fn(scaled_value)
            return scaled_value

        # Unexpected enum value
        if (
            isinstance(self._type_data, EnumTypeData)
            and value not in self._type_data.range
        ):
            return None

        # Valid string or enum value
        return value
