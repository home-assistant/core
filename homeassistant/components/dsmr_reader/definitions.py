"""Definitions for DSMR Reader sensors added to MQTT."""

from homeassistant.const import (
    CURRENCY_EURO,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    VOLT,
    VOLUME_CUBIC_METERS,
)


def dsmr_transform(value):
    """Transform DSMR version value to right format."""
    if value.isdigit():
        return float(value) / 10
    return value


def tariff_transform(value):
    """Transform tariff from number to description."""
    if value == "1":
        return "low"
    return "high"


DEFINITIONS = {
    "dsmr/reading/electricity_delivered_1": {
        "name": "Low tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_returned_1": {
        "name": "Low tariff returned",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_delivered_2": {
        "name": "High tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_returned_2": {
        "name": "High tariff returned",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_currently_delivered": {
        "name": "Current power usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/electricity_currently_returned": {
        "name": "Current power return",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_delivered_l1": {
        "name": "Current power usage L1",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_delivered_l2": {
        "name": "Current power usage L2",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_delivered_l3": {
        "name": "Current power usage L3",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_returned_l1": {
        "name": "Current power return L1",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_returned_l2": {
        "name": "Current power return L2",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/phase_currently_returned_l3": {
        "name": "Current power return L3",
        "enable_default": True,
        "device_class": DEVICE_CLASS_POWER,
        "unit": POWER_KILO_WATT,
    },
    "dsmr/reading/extra_device_delivered": {
        "name": "Gas meter usage",
        "enable_default": True,
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/reading/phase_voltage_l1": {
        "name": "Current voltage L1",
        "enable_default": True,
        "device_class": DEVICE_CLASS_VOLTAGE,
        "unit": VOLT,
    },
    "dsmr/reading/phase_voltage_l2": {
        "name": "Current voltage L2",
        "enable_default": True,
        "device_class": DEVICE_CLASS_VOLTAGE,
        "unit": VOLT,
    },
    "dsmr/reading/phase_voltage_l3": {
        "name": "Current voltage L3",
        "enable_default": True,
        "device_class": DEVICE_CLASS_VOLTAGE,
        "unit": VOLT,
    },
    "dsmr/reading/phase_power_current_l1": {
        "name": "Phase power current L1",
        "enable_default": True,
        "device_class": DEVICE_CLASS_CURRENT,
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/reading/phase_power_current_l2": {
        "name": "Phase power current L2",
        "enable_default": True,
        "device_class": DEVICE_CLASS_CURRENT,
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/reading/phase_power_current_l3": {
        "name": "Phase power current L3",
        "enable_default": True,
        "device_class": DEVICE_CLASS_CURRENT,
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/reading/timestamp": {
        "name": "Telegram timestamp",
        "enable_default": False,
        "device_class": DEVICE_CLASS_TIMESTAMP,
    },
    "dsmr/consumption/gas/delivered": {
        "name": "Gas usage",
        "enable_default": True,
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/consumption/gas/currently_delivered": {
        "name": "Current gas usage",
        "enable_default": True,
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/consumption/gas/read_at": {
        "name": "Gas meter read",
        "enable_default": True,
        "device_class": DEVICE_CLASS_TIMESTAMP,
    },
    "dsmr/day-consumption/electricity1": {
        "name": "Low tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity2": {
        "name": "High tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity1_returned": {
        "name": "Low tariff return",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity2_returned": {
        "name": "High tariff return",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity_merged": {
        "name": "Power usage total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity_returned_merged": {
        "name": "Power return total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity1_cost": {
        "name": "Low tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/electricity2_cost": {
        "name": "High tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/electricity_cost_merged": {
        "name": "Power total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/gas": {
        "name": "Gas usage",
        "enable_default": True,
        "icon": "mdi:counter",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/day-consumption/gas_cost": {
        "name": "Gas cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/total_cost": {
        "name": "Total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_delivered_1": {
        "name": "Low tariff delivered price",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_delivered_2": {
        "name": "High tariff delivered price",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_returned_1": {
        "name": "Low tariff returned price",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_returned_2": {
        "name": "High tariff returned price",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_gas": {
        "name": "Gas price",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/meter-stats/dsmr_version": {
        "name": "DSMR version",
        "enable_default": True,
        "icon": "mdi:alert-circle",
        "transform": dsmr_transform,
    },
    "dsmr/meter-stats/electricity_tariff": {
        "name": "Electricity tariff",
        "enable_default": True,
        "icon": "mdi:flash",
        "transform": tariff_transform,
    },
    "dsmr/meter-stats/power_failure_count": {
        "name": "Power failure count",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/long_power_failure_count": {
        "name": "Long power failure count",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l1": {
        "name": "Voltage sag L1",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l2": {
        "name": "Voltage sag L2",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l3": {
        "name": "Voltage sag L3",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l1": {
        "name": "Voltage swell L1",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l2": {
        "name": "Voltage swell L2",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l3": {
        "name": "Voltage swell L3",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/rejected_telegrams": {
        "name": "Rejected telegrams",
        "enable_default": True,
        "icon": "mdi:flash",
    },
    "dsmr/current-month/electricity1": {
        "name": "Current month low tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity2": {
        "name": "Current month high tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity1_returned": {
        "name": "Current month low tariff returned",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity2_returned": {
        "name": "Current month high tariff returned",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity_merged": {
        "name": "Current month power usage total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity_returned_merged": {
        "name": "Current month power return total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-month/electricity1_cost": {
        "name": "Current month low tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-month/electricity2_cost": {
        "name": "Current month high tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-month/electricity_cost_merged": {
        "name": "Current month power total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-month/gas": {
        "name": "Current month gas usage",
        "enable_default": True,
        "icon": "mdi:counter",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/current-month/gas_cost": {
        "name": "Current month gas cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-month/fixed_cost": {
        "name": "Current month fixed cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-month/total_cost": {
        "name": "Current month total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/electricity1": {
        "name": "Current year low tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity2": {
        "name": "Current year high tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity1_returned": {
        "name": "Current year low tariff returned",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity2_returned": {
        "name": "Current year high tariff usage",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity_merged": {
        "name": "Current year power usage total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity_returned_merged": {
        "name": "Current year power returned total",
        "enable_default": True,
        "device_class": DEVICE_CLASS_ENERGY,
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/current-year/electricity1_cost": {
        "name": "Current year low tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/electricity2_cost": {
        "name": "Current year high tariff cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/electricity_cost_merged": {
        "name": "Current year power total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/gas": {
        "name": "Current year gas usage",
        "enable_default": True,
        "icon": "mdi:counter",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/current-year/gas_cost": {
        "name": "Current year gas cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/fixed_cost": {
        "name": "Current year fixed cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/current-year/total_cost": {
        "name": "Current year total cost",
        "enable_default": True,
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
}
