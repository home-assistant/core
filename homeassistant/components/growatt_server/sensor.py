"""Read status of growatt inverters."""
import datetime
import json
import logging
import re

import growattServer
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CURRENCY_EURO,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    TEMP_CELSIUS,
    VOLT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle, dt

from .const import CONF_PLANT_ID, DEFAULT_NAME, DEFAULT_PLANT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)

# Sensor type order is: Sensor name, Unit of measurement, api data name, additional options
TOTAL_SENSOR_TYPES = {
    "total_money_today": ("Total money today", CURRENCY_EURO, "plantMoneyText", {}),
    "total_money_total": ("Money lifetime", CURRENCY_EURO, "totalMoneyText", {}),
    "total_energy_today": (
        "Energy Today",
        ENERGY_KILO_WATT_HOUR,
        "todayEnergy",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "total_output_power": (
        "Output Power",
        POWER_WATT,
        "invTodayPpv",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "total_energy_output": (
        "Lifetime energy output",
        ENERGY_KILO_WATT_HOUR,
        "totalEnergy",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "total_maximum_output": (
        "Maximum power",
        POWER_WATT,
        "nominalPower",
        {"device_class": DEVICE_CLASS_POWER},
    ),
}

INVERTER_SENSOR_TYPES = {
    "inverter_energy_today": (
        "Energy today",
        ENERGY_KILO_WATT_HOUR,
        "powerToday",
        {"round": 1, "device_class": DEVICE_CLASS_ENERGY},
    ),
    "inverter_energy_total": (
        "Lifetime energy output",
        ENERGY_KILO_WATT_HOUR,
        "powerTotal",
        {"round": 1, "device_class": DEVICE_CLASS_ENERGY},
    ),
    "inverter_voltage_input_1": (
        "Input 1 voltage",
        VOLT,
        "vpv1",
        {"round": 2, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "inverter_amperage_input_1": (
        "Input 1 Amperage",
        ELECTRICAL_CURRENT_AMPERE,
        "ipv1",
        {"round": 1, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "inverter_wattage_input_1": (
        "Input 1 Wattage",
        POWER_WATT,
        "ppv1",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_voltage_input_2": (
        "Input 2 voltage",
        VOLT,
        "vpv2",
        {"round": 1, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "inverter_amperage_input_2": (
        "Input 2 Amperage",
        ELECTRICAL_CURRENT_AMPERE,
        "ipv2",
        {"round": 1, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "inverter_wattage_input_2": (
        "Input 2 Wattage",
        POWER_WATT,
        "ppv2",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_voltage_input_3": (
        "Input 3 voltage",
        VOLT,
        "vpv3",
        {"round": 1, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "inverter_amperage_input_3": (
        "Input 3 Amperage",
        ELECTRICAL_CURRENT_AMPERE,
        "ipv3",
        {"round": 1, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "inverter_wattage_input_3": (
        "Input 3 Wattage",
        POWER_WATT,
        "ppv3",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_internal_wattage": (
        "Internal wattage",
        POWER_WATT,
        "ppv",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_reactive_voltage": (
        "Reactive voltage",
        VOLT,
        "vacr",
        {"round": 1, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "inverter_inverter_reactive_amperage": (
        "Reactive amperage",
        ELECTRICAL_CURRENT_AMPERE,
        "iacr",
        {"round": 1, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "inverter_frequency": ("AC frequency", FREQUENCY_HERTZ, "fac", {"round": 1}),
    "inverter_current_wattage": (
        "Output power",
        POWER_WATT,
        "pac",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_current_reactive_wattage": (
        "Reactive wattage",
        POWER_WATT,
        "pacr",
        {"device_class": DEVICE_CLASS_POWER, "round": 1},
    ),
    "inverter_ipm_temperature": (
        "Intelligent Power Management temperature",
        TEMP_CELSIUS,
        "ipmTemperature",
        {"device_class": DEVICE_CLASS_TEMPERATURE, "round": 1},
    ),
    "inverter_temperature": (
        "Temperature",
        TEMP_CELSIUS,
        "temperature",
        {"device_class": DEVICE_CLASS_TEMPERATURE, "round": 1},
    ),
}

STORAGE_SENSOR_TYPES = {
    "storage_storage_production_today": (
        "Storage production today",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_storage_production_lifetime": (
        "Lifetime Storage production",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_grid_discharge_today": (
        "Grid discharged today",
        ENERGY_KILO_WATT_HOUR,
        "eacDisChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_load_consumption_today": (
        "Load consumption today",
        ENERGY_KILO_WATT_HOUR,
        "eopDischrToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_load_consumption_lifetime": (
        "Lifetime load consumption",
        ENERGY_KILO_WATT_HOUR,
        "eopDischrTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_grid_charged_today": (
        "Grid charged today",
        ENERGY_KILO_WATT_HOUR,
        "eacChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_charge_storage_lifetime": (
        "Lifetime storaged charged",
        ENERGY_KILO_WATT_HOUR,
        "eChargeTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_solar_production": (
        "Solar power production",
        POWER_WATT,
        "ppv",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "storage_battery_percentage": (
        "Battery percentage",
        PERCENTAGE,
        "capacity",
        {"device_class": DEVICE_CLASS_BATTERY},
    ),
    "storage_power_flow": (
        "Storage charging/ discharging(-ve)",
        POWER_WATT,
        "pCharge",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "storage_load_consumption_solar_storage": (
        "Load consumption(Solar + Storage)",
        "VA",
        "rateVA",
        {},
    ),
    "storage_charge_today": (
        "Charge today",
        ENERGY_KILO_WATT_HOUR,
        "eChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_import_from_grid": (
        "Import from grid",
        POWER_WATT,
        "pAcInPut",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "storage_import_from_grid_today": (
        "Import from grid today",
        ENERGY_KILO_WATT_HOUR,
        "eToUserToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_import_from_grid_total": (
        "Import from grid total",
        ENERGY_KILO_WATT_HOUR,
        "eToUserTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "storage_load_consumption": (
        "Load consumption",
        POWER_WATT,
        "outPutPower",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "storage_grid_voltage": (
        "AC input voltage",
        VOLT,
        "vGrid",
        {"round": 2, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "storage_pv_charging_voltage": (
        "PV charging voltage",
        VOLT,
        "vpv",
        {"round": 2, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "storage_ac_input_frequency_out": (
        "AC input frequency",
        FREQUENCY_HERTZ,
        "freqOutPut",
        {"round": 2},
    ),
    "storage_output_voltage": (
        "Output voltage",
        VOLT,
        "outPutVolt",
        {"round": 2, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "storage_ac_output_frequency": (
        "Ac output frequency",
        FREQUENCY_HERTZ,
        "freqGrid",
        {"round": 2},
    ),
    "storage_current_PV": (
        "Solar charge current",
        ELECTRICAL_CURRENT_AMPERE,
        "iAcCharge",
        {"round": 2, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "storage_current_1": (
        "Solar current to storage",
        ELECTRICAL_CURRENT_AMPERE,
        "iChargePV1",
        {"round": 2, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "storage_grid_amperage_input": (
        "Grid charge current",
        ELECTRICAL_CURRENT_AMPERE,
        "chgCurr",
        {"round": 2, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "storage_grid_out_current": (
        "Grid out current",
        ELECTRICAL_CURRENT_AMPERE,
        "outPutCurrent",
        {"round": 2, "device_class": DEVICE_CLASS_CURRENT},
    ),
    "storage_battery_voltage": (
        "Battery voltage",
        VOLT,
        "vBat",
        {"round": 2, "device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "storage_load_percentage": (
        "Load percentage",
        PERCENTAGE,
        "loadPercent",
        {"device_class": DEVICE_CLASS_BATTERY, "round": 2},
    ),
}

MIX_SENSOR_TYPES = {
    # Values from 'mix_info' API call
    "mix_statement_of_charge": (
        "Statement of charge",
        PERCENTAGE,
        "capacity",
        {"device_class": DEVICE_CLASS_BATTERY},
    ),
    "mix_battery_charge_today": (
        "Battery charged today",
        ENERGY_KILO_WATT_HOUR,
        "eBatChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_battery_charge_lifetime": (
        "Lifetime battery charged",
        ENERGY_KILO_WATT_HOUR,
        "eBatChargeTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_battery_discharge_today": (
        "Battery discharged today",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_battery_discharge_lifetime": (
        "Lifetime battery discharged",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_solar_generation_today": (
        "Solar energy today",
        ENERGY_KILO_WATT_HOUR,
        "epvToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_solar_generation_lifetime": (
        "Lifetime solar energy",
        ENERGY_KILO_WATT_HOUR,
        "epvTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_battery_discharge_w": (
        "Battery discharging W",
        POWER_WATT,
        "pDischarge1",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_battery_voltage": (
        "Battery voltage",
        VOLT,
        "vbat",
        {"device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "mix_pv1_voltage": (
        "PV1 voltage",
        VOLT,
        "vpv1",
        {"device_class": DEVICE_CLASS_VOLTAGE},
    ),
    "mix_pv2_voltage": (
        "PV2 voltage",
        VOLT,
        "vpv2",
        {"device_class": DEVICE_CLASS_VOLTAGE},
    ),
    # Values from 'mix_totals' API call
    "mix_load_consumption_today": (
        "Load consumption today",
        ENERGY_KILO_WATT_HOUR,
        "elocalLoadToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_load_consumption_lifetime": (
        "Lifetime load consumption",
        ENERGY_KILO_WATT_HOUR,
        "elocalLoadTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_export_to_grid_today": (
        "Export to grid today",
        ENERGY_KILO_WATT_HOUR,
        "etoGridToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_export_to_grid_lifetime": (
        "Lifetime export to grid",
        ENERGY_KILO_WATT_HOUR,
        "etogridTotal",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    # Values from 'mix_system_status' API call
    "mix_battery_charge": (
        "Battery charging",
        POWER_KILO_WATT,
        "chargePower",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_load_consumption": (
        "Load consumption",
        POWER_KILO_WATT,
        "pLocalLoad",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_wattage_pv_1": (
        "PV1 Wattage",
        POWER_KILO_WATT,
        "pPv1",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_wattage_pv_2": (
        "PV2 Wattage",
        POWER_KILO_WATT,
        "pPv2",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_wattage_pv_all": (
        "All PV Wattage",
        POWER_KILO_WATT,
        "ppv",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_export_to_grid": (
        "Export to grid",
        POWER_KILO_WATT,
        "pactogrid",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_import_from_grid": (
        "Import from grid",
        POWER_KILO_WATT,
        "pactouser",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_battery_discharge_kw": (
        "Battery discharging kW",
        POWER_KILO_WATT,
        "pdisCharge1",
        {"device_class": DEVICE_CLASS_POWER},
    ),
    "mix_grid_voltage": (
        "Grid voltage",
        VOLT,
        "vAc1",
        {"device_class": DEVICE_CLASS_VOLTAGE},
    ),
    # Values from 'mix_detail' API call
    "mix_system_production_today": (
        "System production today (self-consumption + export)",
        ENERGY_KILO_WATT_HOUR,
        "eCharge",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_load_consumption_solar_today": (
        "Load consumption today (solar)",
        ENERGY_KILO_WATT_HOUR,
        "eChargeToday",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_self_consumption_today": (
        "Self consumption today (solar + battery)",
        ENERGY_KILO_WATT_HOUR,
        "eChargeToday1",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_load_consumption_battery_today": (
        "Load consumption today (battery)",
        ENERGY_KILO_WATT_HOUR,
        "echarge1",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    "mix_import_from_grid_today": (
        "Import from grid today (load)",
        ENERGY_KILO_WATT_HOUR,
        "etouser",
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
    # This sensor is manually created using the most recent X-Axis value from the chartData
    "mix_last_update": (
        "Last Data Update",
        None,
        "lastdataupdate",
        {"device_class": DEVICE_CLASS_TIMESTAMP},
    ),
    # Values from 'dashboard_data' API call
    "mix_import_from_grid_today_combined": (
        "Import from grid today (load + charging)",
        ENERGY_KILO_WATT_HOUR,
        "etouser_combined",  # This id is not present in the raw API data, it is added by the sensor
        {"device_class": DEVICE_CLASS_ENERGY},
    ),
}

SENSOR_TYPES = {
    **TOTAL_SENSOR_TYPES,
    **INVERTER_SENSOR_TYPES,
    **STORAGE_SENSOR_TYPES,
    **MIX_SENSOR_TYPES,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PLANT_ID, default=DEFAULT_PLANT_ID): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up growatt server from yaml."""
    if not hass.config_entries.async_entries(DOMAIN):
        _LOGGER.warning(
            "Loading Growatt via platform setup is deprecated."
            "Please remove it from your configuration"
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
        )


def get_device_list(api, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    if not login_response["success"] and login_response["errCode"] == "102":
        _LOGGER.error("Username or Password may be incorrect!")
        return
    user_id = login_response["userId"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    return [devices, plant_id]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Growatt sensor."""
    config = config_entry.data
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    name = config[CONF_NAME]

    api = growattServer.GrowattApi()

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    entities = []
    probe = GrowattData(api, username, password, plant_id, "total")
    for sensor in TOTAL_SENSOR_TYPES:
        entities.append(
            GrowattInverter(probe, f"{name} Total", sensor, f"{plant_id}-{sensor}")
        )

    # Add sensors for each device in the specified plant.
    for device in devices:
        probe = GrowattData(
            api, username, password, device["deviceSn"], device["deviceType"]
        )
        sensors = []
        if device["deviceType"] == "inverter":
            sensors = INVERTER_SENSOR_TYPES
        elif device["deviceType"] == "storage":
            probe.plant_id = plant_id
            sensors = STORAGE_SENSOR_TYPES
        elif device["deviceType"] == "mix":
            probe.plant_id = plant_id
            sensors = MIX_SENSOR_TYPES
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device["deviceType"],
            )

        for sensor in sensors:
            entities.append(
                GrowattInverter(
                    probe,
                    f"{device['deviceAilas']}",
                    sensor,
                    f"{device['deviceSn']}-{sensor}",
                )
            )

    async_add_entities(entities, True)


class GrowattInverter(SensorEntity):
    """Representation of a Growatt Sensor."""

    def __init__(self, probe, name, sensor, unique_id):
        """Initialize a PVOutput sensor."""
        self.sensor = sensor
        self.probe = probe
        self._name = name
        self._state = None
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {SENSOR_TYPES[self.sensor][0]}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:solar-power"

    @property
    def state(self):
        """Return the state of the sensor."""
        result = self.probe.get_data(SENSOR_TYPES[self.sensor][2])
        round_to = SENSOR_TYPES[self.sensor][3].get("round")
        if round_to is not None:
            result = round(result, round_to)
        return result

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self.sensor][3].get("device_class")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self.sensor][1]

    def update(self):
        """Get the latest data from the Growat API and updates the state."""
        self.probe.update()


class GrowattData:
    """The class for handling data retrieval."""

    def __init__(self, api, username, password, device_id, growatt_type):
        """Initialize the probe."""

        self.growatt_type = growatt_type
        self.api = api
        self.device_id = device_id
        self.plant_id = None
        self.data = {}
        self.username = username
        self.password = password

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update probe data."""
        self.api.login(self.username, self.password)
        _LOGGER.debug("Updating data for %s", self.device_id)
        try:
            if self.growatt_type == "total":
                total_info = self.api.plant_info(self.device_id)
                del total_info["deviceList"]
                # PlantMoneyText comes in as "3.1/€" remove anything that isn't part of the number
                total_info["plantMoneyText"] = re.sub(
                    r"[^\d.,]", "", total_info["plantMoneyText"]
                )
                self.data = total_info
            elif self.growatt_type == "inverter":
                inverter_info = self.api.inverter_detail(self.device_id)
                self.data = inverter_info
            elif self.growatt_type == "storage":
                storage_info_detail = self.api.storage_params(self.device_id)[
                    "storageDetailBean"
                ]
                storage_energy_overview = self.api.storage_energy_overview(
                    self.plant_id, self.device_id
                )
                self.data = {**storage_info_detail, **storage_energy_overview}
            elif self.growatt_type == "mix":
                mix_info = self.api.mix_info(self.device_id)
                mix_totals = self.api.mix_totals(self.device_id, self.plant_id)
                mix_system_status = self.api.mix_system_status(
                    self.device_id, self.plant_id
                )

                mix_detail = self.api.mix_detail(self.device_id, self.plant_id)
                # Get the chart data and work out the time of the last entry, use this as the last time data was published to the Growatt Server
                mix_chart_entries = mix_detail["chartData"]
                sorted_keys = sorted(mix_chart_entries)

                # Create datetime from the latest entry
                date_now = dt.now().date()
                last_updated_time = dt.parse_time(str(sorted_keys[-1]))
                combined_timestamp = datetime.datetime.combine(
                    date_now, last_updated_time
                )
                # Convert datetime to UTC
                combined_timestamp_utc = dt.as_utc(combined_timestamp)
                mix_detail["lastdataupdate"] = combined_timestamp_utc.isoformat()

                # Dashboard data is largely inaccurate for mix system but it is the only call with the ability to return the combined
                # imported from grid value that is the combination of charging AND load consumption
                dashboard_data = self.api.dashboard_data(self.plant_id)
                # Dashboard values have units e.g. "kWh" as part of their returned string, so we remove it
                dashboard_values_for_mix = {
                    # etouser is already used by the results from 'mix_detail' so we rebrand it as 'etouser_combined'
                    "etouser_combined": dashboard_data["etouser"].replace("kWh", "")
                }
                self.data = {
                    **mix_info,
                    **mix_totals,
                    **mix_system_status,
                    **mix_detail,
                    **dashboard_values_for_mix,
                }
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)
