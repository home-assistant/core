"""Definitions for DSMR Reader sensors added to MQTT."""

from homeassistant.const import (
    CURRENCY_EURO,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
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
        "icon": "mdi:flash",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_returned_1": {
        "name": "Low tariff returned",
        "icon": "mdi:flash-outline",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_delivered_2": {
        "name": "High tariff usage",
        "icon": "mdi:flash",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_returned_2": {
        "name": "High tariff returned",
        "icon": "mdi:flash-outline",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/reading/electricity_currently_delivered": {
        "name": "Current power usage",
        "icon": "mdi:flash",
        "unit": "kW",
    },
    "dsmr/reading/electricity_currently_returned": {
        "name": "Current power return",
        "icon": "mdi:flash-outline",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_delivered_l1": {
        "name": "Current power usage L1",
        "icon": "mdi:flash",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_delivered_l2": {
        "name": "Current power usage L2",
        "icon": "mdi:flash",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_delivered_l3": {
        "name": "Current power usage L3",
        "icon": "mdi:flash",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_returned_l1": {
        "name": "Current power return L1",
        "icon": "mdi:flash-outline",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_returned_l2": {
        "name": "Current power return L2",
        "icon": "mdi:flash-outline",
        "unit": "kW",
    },
    "dsmr/reading/phase_currently_returned_l3": {
        "name": "Current power return L3",
        "icon": "mdi:flash-outline",
        "unit": "kW",
    },
    "dsmr/reading/extra_device_delivered": {
        "name": "Gas meter usage",
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/reading/phase_voltage_l1": {
        "name": "Current voltage L1",
        "icon": "mdi:flash",
        "unit": VOLT,
    },
    "dsmr/reading/phase_voltage_l2": {
        "name": "Current voltage L2",
        "icon": "mdi:flash",
        "unit": VOLT,
    },
    "dsmr/reading/phase_voltage_l3": {
        "name": "Current voltage L3",
        "icon": "mdi:flash",
        "unit": VOLT,
    },
    "dsmr/reading/phase_power_current_l1": {
        "name": "Phase power current L1",
        "icon": "mdi:flash",
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/reading/phase_power_current_l2": {
        "name": "Phase power current L2",
        "icon": "mdi:flash",
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/reading/phase_power_current_l3": {
        "name": "Phase power current L3",
        "icon": "mdi:flash",
        "unit": ELECTRICAL_CURRENT_AMPERE,
    },
    "dsmr/consumption/gas/delivered": {
        "name": "Gas usage",
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/consumption/gas/currently_delivered": {
        "name": "Current gas usage",
        "icon": "mdi:fire",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/consumption/gas/read_at": {
        "name": "Gas meter read",
        "icon": "mdi:clock",
        "unit": "",
    },
    "dsmr/day-consumption/electricity1": {
        "name": "Low tariff usage",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity2": {
        "name": "High tariff usage",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity1_returned": {
        "name": "Low tariff return",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity2_returned": {
        "name": "High tariff return",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity_merged": {
        "name": "Power usage total",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity_returned_merged": {
        "name": "Power return total",
        "icon": "mdi:counter",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "dsmr/day-consumption/electricity1_cost": {
        "name": "Low tariff cost",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/electricity2_cost": {
        "name": "High tariff cost",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/electricity_cost_merged": {
        "name": "Power total cost",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/gas": {
        "name": "Gas usage",
        "icon": "mdi:counter",
        "unit": VOLUME_CUBIC_METERS,
    },
    "dsmr/day-consumption/gas_cost": {
        "name": "Gas cost",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/total_cost": {
        "name": "Total cost",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_delivered_1": {
        "name": "Low tariff delivered price",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_delivered_2": {
        "name": "High tariff delivered price",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_returned_1": {
        "name": "Low tariff returned price",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_electricity_returned_2": {
        "name": "High tariff returned price",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/day-consumption/energy_supplier_price_gas": {
        "name": "Gas price",
        "icon": "mdi:currency-eur",
        "unit": CURRENCY_EURO,
    },
    "dsmr/meter-stats/dsmr_version": {
        "name": "DSMR version",
        "icon": "mdi:alert-circle",
        "transform": dsmr_transform,
    },
    "dsmr/meter-stats/electricity_tariff": {
        "name": "Electricity tariff",
        "icon": "mdi:flash",
        "transform": tariff_transform,
    },
    "dsmr/meter-stats/power_failure_count": {
        "name": "Power failure count",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/long_power_failure_count": {
        "name": "Long power failure count",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l1": {
        "name": "Voltage sag L1",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l2": {
        "name": "Voltage sag L2",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_sag_count_l3": {
        "name": "Voltage sag L3",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l1": {
        "name": "Voltage swell L1",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l2": {
        "name": "Voltage swell L2",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/voltage_swell_count_l3": {
        "name": "Voltage swell L3",
        "icon": "mdi:flash",
    },
    "dsmr/meter-stats/rejected_telegrams": {
        "name": "Rejected telegrams",
        "icon": "mdi:flash",
    },
}
