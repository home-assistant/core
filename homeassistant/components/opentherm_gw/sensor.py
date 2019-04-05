"""Support for OpenTherm Gateway sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from . import DATA_GATEWAYS, DATA_OPENTHERM_GW

_LOGGER = logging.getLogger(__name__)

UNIT_BAR = 'bar'
UNIT_HOUR = 'h'
UNIT_KW = 'kW'
UNIT_L_MIN = 'L/min'
UNIT_PERCENT = '%'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the OpenTherm Gateway sensors."""
    if discovery_info is None:
        return
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][discovery_info]
    sensor_info = {
        # [device_class, unit, friendly_name]
        gw_dev.vars.DATA_CONTROL_SETPOINT: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Control Setpoint {}"],
        gw_dev.vars.DATA_MASTER_MEMBERID: [
            None, None, "Thermostat Member ID {}"],
        gw_dev.vars.DATA_SLAVE_MEMBERID: [None, None, "Boiler Member ID {}"],
        gw_dev.vars.DATA_SLAVE_OEM_FAULT: [
            None, None, "Boiler OEM Fault Code {}"],
        gw_dev.vars.DATA_COOLING_CONTROL: [
            None, UNIT_PERCENT, "Cooling Control Signal {}"],
        gw_dev.vars.DATA_CONTROL_SETPOINT_2: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Control Setpoint 2 {}"],
        gw_dev.vars.DATA_ROOM_SETPOINT_OVRD: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Room Setpoint Override {}"],
        gw_dev.vars.DATA_SLAVE_MAX_RELATIVE_MOD: [
            None, UNIT_PERCENT, "Boiler Maximum Relative Modulation {}"],
        gw_dev.vars.DATA_SLAVE_MAX_CAPACITY: [
            None, UNIT_KW, "Boiler Maximum Capacity {}"],
        gw_dev.vars.DATA_SLAVE_MIN_MOD_LEVEL: [
            None, UNIT_PERCENT, "Boiler Minimum Modulation Level {}"],
        gw_dev.vars.DATA_ROOM_SETPOINT: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Room Setpoint {}"],
        gw_dev.vars.DATA_REL_MOD_LEVEL: [
            None, UNIT_PERCENT, "Relative Modulation Level {}"],
        gw_dev.vars.DATA_CH_WATER_PRESS: [
            None, UNIT_BAR, "Central Heating Water Pressure {}"],
        gw_dev.vars.DATA_DHW_FLOW_RATE: [
            None, UNIT_L_MIN, "Hot Water Flow Rate {}"],
        gw_dev.vars.DATA_ROOM_SETPOINT_2: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Room Setpoint 2 {}"],
        gw_dev.vars.DATA_ROOM_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Room Temperature {}"],
        gw_dev.vars.DATA_CH_WATER_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Central Heating Water Temperature {}"],
        gw_dev.vars.DATA_DHW_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Hot Water Temperature {}"],
        gw_dev.vars.DATA_OUTSIDE_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Outside Temperature {}"],
        gw_dev.vars.DATA_RETURN_WATER_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Return Water Temperature {}"],
        gw_dev.vars.DATA_SOLAR_STORAGE_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Solar Storage Temperature {}"],
        gw_dev.vars.DATA_SOLAR_COLL_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Solar Collector Temperature {}"],
        gw_dev.vars.DATA_CH_WATER_TEMP_2: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Central Heating 2 Water Temperature {}"],
        gw_dev.vars.DATA_DHW_TEMP_2: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Hot Water 2 Temperature {}"],
        gw_dev.vars.DATA_EXHAUST_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Exhaust Temperature {}"],
        gw_dev.vars.DATA_SLAVE_DHW_MAX_SETP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Hot Water Maximum Setpoint {}"],
        gw_dev.vars.DATA_SLAVE_DHW_MIN_SETP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Hot Water Minimum Setpoint {}"],
        gw_dev.vars.DATA_SLAVE_CH_MAX_SETP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Boiler Maximum Central Heating Setpoint {}"],
        gw_dev.vars.DATA_SLAVE_CH_MIN_SETP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Boiler Minimum Central Heating Setpoint {}"],
        gw_dev.vars.DATA_DHW_SETPOINT: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, "Hot Water Setpoint {}"],
        gw_dev.vars.DATA_MAX_CH_SETPOINT: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Maximum Central Heating Setpoint {}"],
        gw_dev.vars.DATA_OEM_DIAG: [None, None, "OEM Diagnostic Code {}"],
        gw_dev.vars.DATA_TOTAL_BURNER_STARTS: [
            None, None, "Total Burner Starts {}"],
        gw_dev.vars.DATA_CH_PUMP_STARTS: [
            None, None, "Central Heating Pump Starts {}"],
        gw_dev.vars.DATA_DHW_PUMP_STARTS: [
            None, None, "Hot Water Pump Starts {}"],
        gw_dev.vars.DATA_DHW_BURNER_STARTS: [
            None, None, "Hot Water Burner Starts {}"],
        gw_dev.vars.DATA_TOTAL_BURNER_HOURS: [
            None, UNIT_HOUR, "Total Burner Hours {}"],
        gw_dev.vars.DATA_CH_PUMP_HOURS: [
            None, UNIT_HOUR, "Central Heating Pump Hours {}"],
        gw_dev.vars.DATA_DHW_PUMP_HOURS: [
            None, UNIT_HOUR, "Hot Water Pump Hours {}"],
        gw_dev.vars.DATA_DHW_BURNER_HOURS: [
            None, UNIT_HOUR, "Hot Water Burner Hours {}"],
        gw_dev.vars.DATA_MASTER_OT_VERSION: [
            None, None, "Thermostat OpenTherm Version {}"],
        gw_dev.vars.DATA_SLAVE_OT_VERSION: [
            None, None, "Boiler OpenTherm Version {}"],
        gw_dev.vars.DATA_MASTER_PRODUCT_TYPE: [
            None, None, "Thermostat Product Type {}"],
        gw_dev.vars.DATA_MASTER_PRODUCT_VERSION: [
            None, None, "Thermostat Product Version {}"],
        gw_dev.vars.DATA_SLAVE_PRODUCT_TYPE: [
            None, None, "Boiler Product Type {}"],
        gw_dev.vars.DATA_SLAVE_PRODUCT_VERSION: [
            None, None, "Boiler Product Version {}"],
        gw_dev.vars.OTGW_MODE: [None, None, "Gateway/Monitor Mode {}"],
        gw_dev.vars.OTGW_DHW_OVRD: [
            None, None, "Gateway Hot Water Override Mode {}"],
        gw_dev.vars.OTGW_ABOUT: [None, None, "Gateway Firmware Version {}"],
        gw_dev.vars.OTGW_BUILD: [None, None, "Gateway Firmware Build {}"],
        gw_dev.vars.OTGW_CLOCKMHZ: [None, None, "Gateway Clock Speed {}"],
        gw_dev.vars.OTGW_LED_A: [None, None, "Gateway LED A Mode {}"],
        gw_dev.vars.OTGW_LED_B: [None, None, "Gateway LED B Mode {}"],
        gw_dev.vars.OTGW_LED_C: [None, None, "Gateway LED C Mode {}"],
        gw_dev.vars.OTGW_LED_D: [None, None, "Gateway LED D Mode {}"],
        gw_dev.vars.OTGW_LED_E: [None, None, "Gateway LED E Mode {}"],
        gw_dev.vars.OTGW_LED_F: [None, None, "Gateway LED F Mode {}"],
        gw_dev.vars.OTGW_GPIO_A: [None, None, "Gateway GPIO A Mode {}"],
        gw_dev.vars.OTGW_GPIO_B: [None, None, "Gateway GPIO B Mode {}"],
        gw_dev.vars.OTGW_SB_TEMP: [
            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
            "Gateway Setback Temperature {}"],
        gw_dev.vars.OTGW_SETP_OVRD_MODE: [
            None, None, "Gateway Room Setpoint Override Mode {}"],
        gw_dev.vars.OTGW_SMART_PWR: [
            None, None, "Gateway Smart Power Mode {}"],
        gw_dev.vars.OTGW_THRM_DETECT: [
            None, None, "Gateway Thermostat Detection {}"],
        gw_dev.vars.OTGW_VREF: [
            None, None, "Gateway Reference Voltage Setting {}"],
    }
    sensors = []
    for var in gw_dev.sensors:
        device_class = sensor_info[var][0]
        unit = sensor_info[var][1]
        friendly_name_format = sensor_info[var][2]
        sensors.append(
            OpenThermSensor(gw_dev, var, device_class, unit,
                            friendly_name_format))
    async_add_entities(sensors)


class OpenThermSensor(Entity):
    """Representation of an OpenTherm Gateway sensor."""

    def __init__(self, gw_dev, var, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, '{}_{}'.format(var, gw_dev.gw_id),
            hass=gw_dev.hass)
        self._gateway = gw_dev
        self._var = var
        self._value = None
        self._device_class = device_class
        self._unit = unit
        self._friendly_name = friendly_name_format.format(gw_dev.name)

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway sensor %s", self._friendly_name)
        async_dispatcher_connect(self.hass, self._gateway.update_signal,
                                 self.receive_report)

    async def receive_report(self, status):
        """Handle status updates from the component."""
        value = status.get(self._var)
        if isinstance(value, float):
            value = '{:2.1f}'.format(value)
        self._value = value
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name of the sensor."""
        return self._friendly_name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def should_poll(self):
        """Return False because entity pushes its state."""
        return False
