"""Read status of growatt inverters."""
import datetime
import logging
import json

import growattServer

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

CONF_PLANT_ID = "plant_id"
DEFAULT_PLANT_ID = "0"
DEFAULT_NAME = "Growatt"
SCAN_INTERVAL = datetime.timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PLANT_ID, default=DEFAULT_PLANT_ID): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    plant_id = config.get(CONF_PLANT_ID)
    name = config.get(CONF_NAME)

    api = growattServer.GrowattApi()

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(username, password)
    if not login_response["success"] and login_response["errCode"] == "102":
        _LOGGER.error("Username or Password may be incorrect!")
        return
    user_id = login_response["userId"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of inverters for specified plant to add sensors for.
    inverters = api.inverter_list(plant_id)

    entities = [GrowattInverter(api, f"{name}_Total", plant_id, username, password)]

    # Add sensors for each inverter in the specified plant.
    for inverter in inverters:
        entities.append(
            GrowattInverter(
                api,
                f"{name}_{inverter['deviceAilas']}",
                inverter["deviceSn"],
                username,
                password,
            )
        )

    add_entities(entities, True)


class GrowattInverter(Entity):
    """Representation of a Growatt Sensor."""

    def __init__(self, api, name, inverter_id, username, password):
        """Initialize a PVOutput sensor."""
        self.api = api
        self._name = name
        self.inverter_id = inverter_id
        self.username = username
        self.password = password
        self.is_total = "Total" in name and inverter_id.isdigit()
        self._state = None
        self.attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:solar-power"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return "power"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "W"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        attributes = self.attributes
        return attributes

    def update(self):
        """Get the latest data from the Growat API and updates the state."""

        try:
            self.api.login(self.username, self.password)
            if self.is_total:
                total_info = self.api.plant_info(self.inverter_id)
                del total_info["deviceList"]
                self._state = total_info["invTodayPpv"]
                self.attributes = {
                    "money_today": total_info["plantMoneyText"],
                    "money_total": total_info["totalMoneyText"],
                    "energy_today": total_info["todayEnergy"],
                    "current_wattage": total_info["invTodayPpv"],
                    "current_voltage": total_info["totalEnergy"],
                    "maximum_output": total_info["nominalPower"],
                }
            else:
                inverter_info = self.api.inverter_detail(self.inverter_id)

                self._state = inverter_info["data"]["pac"]
                self.attributes = {
                    "energy_today": inverter_info["data"]["e_today"],
                    "energy_total": inverter_info["data"]["e_total"],
                    "voltage_input_1": inverter_info["data"]["vpv1"],
                    "amperage_input_1": inverter_info["data"]["ipv1"],
                    "wattage_input_1": inverter_info["data"]["ppv1"],
                    "voltage_input_2": inverter_info["data"]["vpv2"],
                    "amperage_input_2": inverter_info["data"]["ipv2"],
                    "wattage_input_2": inverter_info["data"]["ppv2"],
                    "voltage_input_3": inverter_info["data"]["vpv3"],
                    "amperage_input_3": inverter_info["data"]["ipv3"],
                    "wattage_input_3": inverter_info["data"]["ppv3"],
                    "inverter_internal_wattage": inverter_info["data"]["ppv"],
                    "inverter_reactive_voltage": inverter_info["data"]["vacr"],
                    "inverter_reactive_amperage": inverter_info["data"]["iacr"],
                    "frequency": inverter_info["data"]["fac"],
                    "current_wattage": inverter_info["data"]["pac"],
                    "current_reactive_wattage": inverter_info["data"]["pacr"],
                    "fault": inverter_info["data"]["strfault"],
                    "warning": inverter_info["data"]["strwarning"],
                    "break": inverter_info["data"]["strbreak"],
                    "warning_id": inverter_info["data"]["pidwarning"],
                }
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")
