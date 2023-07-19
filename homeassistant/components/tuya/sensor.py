"""Support for Tuya sensors."""
from __future__ import annotations

from dataclasses import dataclass

from tuya_iot import TuyaDevice, TuyaDeviceManager
from tuya_iot.device import TuyaDeviceStatusRange

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeAssistantTuyaData
from .base import ElectricityTypeData, EnumTypeData, IntegerTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
    DPType,
    UnitOfMeasurement,
)


@dataclass
class TuyaSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""

    subkey: str | None = None


# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_PERCENTAGE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_STATE,
        translation_key="battery_state",
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_VALUE,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.VA_BATTERY,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.RESIDUAL_ELECTRICITY,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery",
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[TuyaSensorEntityDescription, ...]] = {
    # Multi-functional Sensor
    # https://developer.tuya.com/en/docs/iot/categorydgnbj?id=Kaiuz3yorvzg3
    "dgnbj": (
        TuyaSensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            translation_key="gas",
            icon="mdi:gas-cylinder",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            translation_key="gas",
            name="Methane",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO_VALUE,
            translation_key="carbon_monoxide",
            icon="mdi:molecule-co",
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            icon="mdi:molecule-co2",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="luminosity",
            icon="mdi:brightness-6",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            icon="mdi:brightness-6",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            translation_key="smoke_amount",
            icon="mdi:smoke-detector",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_F,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.STATUS,
            translation_key="status",
        ),
    ),
    # CO2 Detector
    # https://developer.tuya.com/en/docs/iot/categoryco2bj?id=Kaiuz3wes7yuy
    "co2bj": (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Two-way temperature and humidity switch
    # "MOES Temperature and Humidity Smart Switch Module MS-103"
    # Documentation not found
    "wkcz": (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # CO Detector
    # https://developer.tuya.com/en/docs/iot/categorycobj?id=Kaiuz3u1j6q1v
    "cobj": (
        TuyaSensorEntityDescription(
            key=DPCode.CO_VALUE,
            translation_key="carbon_monoxide",
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        TuyaSensorEntityDescription(
            key=DPCode.FEED_REPORT,
            translation_key="last_amount",
            icon="mdi:counter",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Air Quality Monitor
    # No specification on Tuya portal
    "hjjcy": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Formaldehyde Detector
    # Note: Not documented
    "jqbj": (
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Methane Detector
    # https://developer.tuya.com/en/docs/iot/categoryjwbj?id=Kaiuz40u98lkm
    "jwbj": (
        TuyaSensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            translation_key="methane",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    # IoT Switch
    # Note: Undocumented
    "tdq": (
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    # Luminance Sensor
    # https://developer.tuya.com/en/docs/iot/categoryldcg?id=Kaiuz3n7u69l8
    "ldcg": (
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="luminosity",
            icon="mdi:brightness-6",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Door and Window Controller
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r5zjsy9
    "mc": BATTERY_SENSORS,
    # Door Window Sensor
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m
    "mcs": BATTERY_SENSORS,
    # Smart Lock
    # https://developer.tuya.com/en/docs/iot/f?id=Kb0o2vbzuzl81
    "ms": (
        TuyaSensorEntityDescription(
            key=DPCode.ALARM_LOCK,
            icon="mdi:information-outline",
            translation_key="lock_alarm",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLOSED_OPENED,
            icon="mdi:lock",
            translation_key="lock_status",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ANTILOCK_STATUS,
            icon="mdi:lock-check",
            translation_key="lock_antilock",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.INSURANCE_STATUS,
            icon="mdi:lock-check",
            translation_key="lock_insurance",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_FINGERPRINT,
            icon="mdi:fingerprint",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_fingerprint",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_PASSWORD,
            icon="mdi:form-textbox-password",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_password",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_TEMPORARY,
            icon="mdi:form-textbox-password",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_temporary_password",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_DYNAMIC,
            icon="mdi:form-textbox-password",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_dynamic_password",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_CARD,
            icon="mdi:card-bulleted-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_card",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_IDENITY_CARD,
            icon="mdi:card-account-details-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_identity_card",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_FACE,
            icon="mdi:face-recognition",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_face_recognition",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_KEY,
            icon="mdi:key-chain-variant",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_mechanical_key",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_EYE,
            icon="mdi:eye-check-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_iris",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_HAND,
            icon="mdi:hand-back-left-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_palm_print",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_FINGER_VEIN,
            icon="mdi:hand-pointing-up",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_finger_vein",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_BLE,
            icon="mdi:bluetooth",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_bluetooth",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_REMOTE,
            icon="mdi:wan",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_remote",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_PHONE_REMOTE,
            icon="mdi:cellphone-key",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_mobile_phone",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_VOICE_REMOTE,
            icon="mdi:cellphone-key",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_voice",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_APP,
            icon="mdi:open-in-app",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_app",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_ACCESS_CONTROL,
            icon="mdi:account-circle-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_access_control_system",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_EMERGENCY,
            icon="mdi:car-brake-alert",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_emergency_password",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_ADMIN,
            icon="mdi:account-check-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_administrator",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNLOCK_SUBADMIN,
            icon="mdi:account-check-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="lock_last_housekeeper",
        ),
        *BATTERY_SENSORS,
    ),
    # Sous Vide Cooker
    # https://developer.tuya.com/en/docs/iot/categorymzj?id=Kaiuz2vy130ux
    "mzj": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.STATUS,
            translation_key="sous_vide_status",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.REMAIN_TIME,
            translation_key="remaining_time",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            icon="mdi:timer",
        ),
    ),
    # PIR Detector
    # https://developer.tuya.com/en/docs/iot/categorypir?id=Kaiuz3ss11b80
    "pir": BATTERY_SENSORS,
    # PM2.5 Sensor
    # https://developer.tuya.com/en/docs/iot/categorypm25?id=Kaiuz3qof3yfu
    "pm2.5": (
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM1,
            translation_key="pm1",
            device_class=SensorDeviceClass.PM1,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM10,
            translation_key="pm10",
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Gas Detector
    # https://developer.tuya.com/en/docs/iot/categoryrqbj?id=Kaiuz3d162ubw
    "rqbj": (
        TuyaSensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            name=None,
            icon="mdi:gas-cylinder",
            state_class=SensorStateClass.MEASUREMENT,
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
        TuyaSensorEntityDescription(
            key=DPCode.SENSOR_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SENSOR_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WIRELESS_ELECTRICITY,
            translation_key="battery",
            device_class=SensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Fingerbot
    "szjqr": BATTERY_SENSORS,
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": BATTERY_SENSORS,
    # Volatile Organic Compound Sensor
    # Note: Undocumented in cloud API docs, based on test device
    "voc": (
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": BATTERY_SENSORS,
    # Temperature and Humidity Sensor
    # https://developer.tuya.com/en/docs/iot/categorywsdcg?id=Kaiuz3hinij34
    "wsdcg": (
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Pressure Sensor
    # https://developer.tuya.com/en/docs/iot/categoryylcg?id=Kaiuz3kc2e4gm
    "ylcg": (
        TuyaSensorEntityDescription(
            key=DPCode.PRESSURE_VALUE,
            name=None,
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Smoke Detector
    # https://developer.tuya.com/en/docs/iot/categoryywbj?id=Kaiuz3f6sf952
    "ywbj": (
        TuyaSensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            translation_key="smoke_amount",
            icon="mdi:smoke-detector",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": BATTERY_SENSORS,
    # Smart Electricity Meter
    # https://developer.tuya.com/en/docs/iot/smart-meter?id=Kaiuz4gv6ack7
    "zndb": (
        TuyaSensorEntityDescription(
            key=DPCode.FORWARD_ENERGY_TOTAL,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
    ),
    # Circuit Breaker
    # https://developer.tuya.com/en/docs/iot/dlq?id=Kb0kidk9enyh8
    "dlq": (
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_FORWARD_ENERGY,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_AREA,
            translation_key="cleaning_area",
            icon="mdi:texture-box",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_TIME,
            translation_key="cleaning_time",
            icon="mdi:progress-clock",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_AREA,
            translation_key="total_cleaning_area",
            icon="mdi:texture-box",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_TIME,
            translation_key="total_cleaning_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_COUNT,
            translation_key="total_cleaning_times",
            icon="mdi:counter",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DUSTER_CLOTH,
            translation_key="duster_cloth_life",
            icon="mdi:ticket-percent-outline",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.EDGE_BRUSH,
            translation_key="side_brush_life",
            icon="mdi:ticket-percent-outline",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.FILTER_LIFE,
            translation_key="filter_life",
            icon="mdi:ticket-percent-outline",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ROLL_BRUSH,
            translation_key="rolling_brush_life",
            icon="mdi:ticket-percent-outline",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Curtain
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48qy7wkre
    "cl": (
        TuyaSensorEntityDescription(
            key=DPCode.TIME_TOTAL,
            translation_key="last_operation_duration",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:progress-clock",
        ),
    ),
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48qwjz0i3
    "jsq": (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_CURRENT,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_F,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LEVEL_CURRENT,
            translation_key="water_level",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:waves-arrow-up",
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r41mn81
    "kj": (
        TuyaSensorEntityDescription(
            key=DPCode.FILTER,
            translation_key="filter_utilization",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:ticket-percent-outline",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:molecule",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TVOC,
            translation_key="total_volatile_organic_compound",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ECO2,
            translation_key="concentration_carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_TIME,
            translation_key="total_operating_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_PM,
            translation_key="total_absorption_particles",
            icon="mdi:texture-box",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.AIR_QUALITY,
            translation_key="air_quality",
            icon="mdi:air-filter",
        ),
    ),
    # Fan
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48quojr54
    "fs": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # eMylo Smart WiFi IR Remote
    "wnykq": (
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Dehumidifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r6jke8e
    "cs": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_INDOOR,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_INDOOR,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Soil sensor (Plant monitor)
    "zwjcy": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["pc"] = SENSORS["kg"]

# Lock (duplicate of 'ms')
# https://developer.tuya.com/en/docs/iot/f?id=Kb0o2vbzuzl81
SENSORS["bxx"] = SENSORS["ms"]
SENSORS["gyms"] = SENSORS["ms"]
SENSORS["jtmspro"] = SENSORS["ms"]
SENSORS["hotelms"] = SENSORS["ms"]
SENSORS["ms_category"] = SENSORS["ms"]
SENSORS["jtmsbh"] = SENSORS["ms"]
SENSORS["mk"] = SENSORS["ms"]
SENSORS["videolock"] = SENSORS["ms"]
SENSORS["photolock"] = SENSORS["ms"]


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
                    if description.key in device.status:
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

    entity_description: TuyaSensorEntityDescription

    _status_range: TuyaDeviceStatusRange | None = None
    _type: DPType | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaSensorEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = (
            f"{super().unique_id}{description.key}{description.subkey or ''}"
        )

        if int_type := self.find_dpcode(description.key, dptype=DPType.INTEGER):
            self._type_data = int_type
            self._type = DPType.INTEGER
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit
        elif enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._type_data = enum_type
            self._type = DPType.ENUM
        else:
            self._type = self.get_dptype(DPCode(description.key))

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
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # If we still have a device class, we should not use an icon
            if self.device_class:
                self._attr_icon = None

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # Only continue if data type is known
        if self._type not in (
            DPType.INTEGER,
            DPType.STRING,
            DPType.ENUM,
            DPType.JSON,
            DPType.RAW,
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

        # Get subkey value from Json string.
        if self._type is DPType.JSON:
            if self.entity_description.subkey is None:
                return None
            values = ElectricityTypeData.from_json(value)
            return getattr(values, self.entity_description.subkey)

        if self._type is DPType.RAW:
            if self.entity_description.subkey is None:
                return None
            values = ElectricityTypeData.from_raw(value)
            return getattr(values, self.entity_description.subkey)

        # Valid string or enum value
        return value
