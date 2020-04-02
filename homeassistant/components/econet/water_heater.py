"""Support for Rheem EcoNet water heaters."""
import datetime
import logging

from pyeconet.api import PyEcoNet
import voluptuous as vol

from homeassistant.components.water_heater import (
    PLATFORM_SCHEMA,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterDevice,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_ADD_VACATION, SERVICE_DELETE_VACATION

_LOGGER = logging.getLogger(__name__)

ATTR_VACATION_START = "next_vacation_start_date"
ATTR_VACATION_END = "next_vacation_end_date"
ATTR_ON_VACATION = "on_vacation"
ATTR_TODAYS_ENERGY_USAGE = "todays_energy_usage"
ATTR_IN_USE = "in_use"

ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

ATTR_LOWER_TEMP = "lower_temp"
ATTR_UPPER_TEMP = "upper_temp"
ATTR_AMBIENT_TEMP = "ambient_temp"
ATTR_IS_ENABLED = "is_enabled"

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

ADD_VACATION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_START_DATE): cv.positive_int,
        vol.Required(ATTR_END_DATE): cv.positive_int,
    }
)

DELETE_VACATION_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

ECONET_DATA = "econet"

ECONET_STATE_TO_HA = {
    "Energy Saver": STATE_ECO,
    "gas": STATE_GAS,
    "High Demand": STATE_HIGH_DEMAND,
    "Off": STATE_OFF,
    "Performance": STATE_PERFORMANCE,
    "Heat Pump Only": STATE_HEAT_PUMP,
    "Electric-Only": STATE_ELECTRIC,
    "Electric": STATE_ELECTRIC,
    "Heat Pump": STATE_HEAT_PUMP,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the EcoNet water heaters."""

    hass.data[ECONET_DATA] = {}
    hass.data[ECONET_DATA]["water_heaters"] = []

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    econet = PyEcoNet(username, password)
    water_heaters = econet.get_water_heaters()
    hass_water_heaters = [
        EcoNetWaterHeater(water_heater) for water_heater in water_heaters
    ]
    add_entities(hass_water_heaters)
    hass.data[ECONET_DATA]["water_heaters"].extend(hass_water_heaters)

    def service_handle(service):
        """Handle the service calls."""
        entity_ids = service.data.get("entity_id")
        all_heaters = hass.data[ECONET_DATA]["water_heaters"]
        _heaters = [
            x for x in all_heaters if not entity_ids or x.entity_id in entity_ids
        ]

        for _water_heater in _heaters:
            if service.service == SERVICE_ADD_VACATION:
                start = service.data.get(ATTR_START_DATE)
                end = service.data.get(ATTR_END_DATE)
                _water_heater.add_vacation(start, end)
            if service.service == SERVICE_DELETE_VACATION:
                for vacation in _water_heater.water_heater.vacations:
                    vacation.delete()

            _water_heater.schedule_update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_ADD_VACATION, service_handle, schema=ADD_VACATION_SCHEMA
    )

    hass.services.register(
        DOMAIN, SERVICE_DELETE_VACATION, service_handle, schema=DELETE_VACATION_SCHEMA
    )


class EcoNetWaterHeater(WaterHeaterDevice):
    """Representation of an EcoNet water heater."""

    def __init__(self, water_heater):
        """Initialize the water heater."""
        self.water_heater = water_heater
        self.supported_modes = self.water_heater.supported_modes
        self.econet_state_to_ha = {}
        self.ha_state_to_econet = {}
        for mode in ECONET_STATE_TO_HA:
            if mode in self.supported_modes:
                self.econet_state_to_ha[mode] = ECONET_STATE_TO_HA.get(mode)
        for key, value in self.econet_state_to_ha.items():
            self.ha_state_to_econet[value] = key
        for mode in self.supported_modes:
            if mode not in ECONET_STATE_TO_HA:
                error = (
                    "Invalid operation mode mapping. "
                    + mode
                    + " doesn't map. Please report this."
                )
                _LOGGER.error(error)

    @property
    def name(self):
        """Return the device name."""
        return self.water_heater.name

    @property
    def available(self):
        """Return if the the device is online or not."""
        return self.water_heater.is_connected

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        vacations = self.water_heater.get_vacations()
        if vacations:
            data[ATTR_VACATION_START] = vacations[0].start_date
            data[ATTR_VACATION_END] = vacations[0].end_date
        data[ATTR_ON_VACATION] = self.water_heater.is_on_vacation
        todays_usage = self.water_heater.total_usage_for_today
        if todays_usage:
            data[ATTR_TODAYS_ENERGY_USAGE] = todays_usage
        data[ATTR_IN_USE] = self.water_heater.in_use

        data[ATTR_LOWER_TEMP] = round(self.water_heater.lower_temp, 2)
        data[ATTR_UPPER_TEMP] = round(self.water_heater.upper_temp, 2)
        data[ATTR_AMBIENT_TEMP] = round(self.water_heater.ambient_temp, 2)
        data[ATTR_IS_ENABLED] = self.water_heater.is_enabled

        return data

    @property
    def current_operation(self):
        """
        Return current operation as one of the following.

        ["eco", "heat_pump", "high_demand", "electric_only"]
        """
        current_op = self.econet_state_to_ha.get(self.water_heater.mode)
        return current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = []
        for mode in self.supported_modes:
            ha_mode = self.econet_state_to_ha.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
        return op_list

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            self.water_heater.set_target_set_point(target_temp)
        else:
            _LOGGER.error("A target temperature must be provided")

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = self.ha_state_to_econet.get(operation_mode)
        if op_mode_to_set is not None:
            self.water_heater.set_mode(op_mode_to_set)
        else:
            _LOGGER.error("An operation mode must be provided")

    def add_vacation(self, start, end):
        """Add a vacation to this water heater."""
        if not start:
            start = datetime.datetime.now()
        else:
            start = datetime.datetime.fromtimestamp(start)
        end = datetime.datetime.fromtimestamp(end)
        self.water_heater.set_vacation_mode(start, end)

    def update(self):
        """Get the latest date."""
        self.water_heater.update_state()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.water_heater.set_point

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.water_heater.min_set_point

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.water_heater.max_set_point
