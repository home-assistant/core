"""Constants for the Leneda integration."""

from datetime import timedelta

from leneda.obis_codes import ObisCode

DOMAIN = "leneda"

CONF_API_TOKEN = "api_token"
CONF_ENERGY_ID = "energy_id"
CONF_METERING_POINTS = "metering_points"

SCAN_INTERVAL = timedelta(hours=1)

# Sensor types and their corresponding OBIS codes
SENSOR_TYPES = {
    # Electricity Consumption
    "electricity_consumption_active": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_ACTIVE,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_consumption_reactive": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_REACTIVE,
        "icon": "mdi:lightning-bolt",
        "device_class": None,  # Ideally SensorDeviceClass.REACTIVE_POWER per hour
        "state_class": "total_increasing",
    },
    "electricity_consumption_covered_layer1": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_COVERED_LAYER1,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_consumption_covered_layer2": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_COVERED_LAYER2,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_consumption_covered_layer3": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_COVERED_LAYER3,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_consumption_covered_layer4": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_COVERED_LAYER4,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_consumption_remaining": {
        "obis_code": ObisCode.ELEC_CONSUMPTION_REMAINING,
        "icon": "mdi:lightning-bolt",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    # Electricity Production
    "electricity_production_active": {
        "obis_code": ObisCode.ELEC_PRODUCTION_ACTIVE,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_production_reactive": {
        "obis_code": ObisCode.ELEC_PRODUCTION_REACTIVE,
        "icon": "mdi:solar-power",
        "device_class": None,  # Ideally SensorDeviceClass.REACTIVE_POWER per hour
        "state_class": "total_increasing",
    },
    "electricity_production_shared_layer1": {
        "obis_code": ObisCode.ELEC_PRODUCTION_SHARED_LAYER1,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_production_shared_layer2": {
        "obis_code": ObisCode.ELEC_PRODUCTION_SHARED_LAYER2,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_production_shared_layer3": {
        "obis_code": ObisCode.ELEC_PRODUCTION_SHARED_LAYER3,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_production_shared_layer4": {
        "obis_code": ObisCode.ELEC_PRODUCTION_SHARED_LAYER4,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "electricity_production_remaining": {
        "obis_code": ObisCode.ELEC_PRODUCTION_REMAINING,
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    # Gas Consumption
    "gas_consumption_volume": {
        "obis_code": ObisCode.GAS_CONSUMPTION_VOLUME,
        "icon": "mdi:fire",
        "device_class": "gas",
        "state_class": "total_increasing",
    },
    "gas_consumption_standard_volume": {
        "obis_code": ObisCode.GAS_CONSUMPTION_STANDARD_VOLUME,
        "icon": "mdi:fire",
        "device_class": None,  # Ideally SensorDeviceClass.GAS, but Nm3 not supported by Hass
        "state_class": "total_increasing",
    },
    "gas_consumption_energy": {
        "obis_code": ObisCode.GAS_CONSUMPTION_ENERGY,
        "icon": "mdi:fire",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
}

UNIT_TO_AGGREGATED_UNIT = {"kW": "kWh", "kVAR": "kVARh"}

# Integration description
INTEGRATION_DESCRIPTION = """
Leneda Integration for Home Assistant

This integration allows you to monitor your energy consumption and production from the Leneda energy platform in Luxembourg.

Features:
- Track electricity consumption and production
- Monitor gas consumption
- Yearly energy tracking (resets on January 1st)
- Compatible with Home Assistant Energy Dashboard

Note: Data is updated hourly and may have a one-day lag as per Leneda's data availability.
"""
