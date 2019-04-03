"""Support for OpenTherm Gateway binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT, BinarySensorDevice)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id

from . import DATA_GATEWAYS, DATA_OPENTHERM_GW

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_COLD = 'cold'
DEVICE_CLASS_HEAT = 'heat'
DEVICE_CLASS_PROBLEM = 'problem'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the OpenTherm Gateway binary sensors."""
    if discovery_info is None:
        return
    gw = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][discovery_info]
    sensor_info = {
        # [device_class, friendly_name format]
        gw.vars.DATA_MASTER_CH_ENABLED: [
            None, "Thermostat Central Heating Enabled {}"],
        gw.vars.DATA_MASTER_DHW_ENABLED: [
            None, "Thermostat Hot Water Enabled {}"],
        gw.vars.DATA_MASTER_COOLING_ENABLED: [
            None, "Thermostat Cooling Enabled {}"],
        gw.vars.DATA_MASTER_OTC_ENABLED: [
            None, "Thermostat Outside Temperature Correction Enabled {}"],
        gw.vars.DATA_MASTER_CH2_ENABLED: [
            None, "Thermostat Central Heating 2 Enabled {}"],
        gw.vars.DATA_SLAVE_FAULT_IND: [
            DEVICE_CLASS_PROBLEM, "Boiler Fault Indication {}"],
        gw.vars.DATA_SLAVE_CH_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Central Heating Status {}"],
        gw.vars.DATA_SLAVE_DHW_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Hot Water Status {}"],
        gw.vars.DATA_SLAVE_FLAME_ON: [
            DEVICE_CLASS_HEAT, "Boiler Flame Status {}"],
        gw.vars.DATA_SLAVE_COOLING_ACTIVE: [
            DEVICE_CLASS_COLD, "Boiler Cooling Status {}"],
        gw.vars.DATA_SLAVE_CH2_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Central Heating 2 Status {}"],
        gw.vars.DATA_SLAVE_DIAG_IND: [
            DEVICE_CLASS_PROBLEM, "Boiler Diagnostics Indication {}"],
        gw.vars.DATA_SLAVE_DHW_PRESENT: [None, "Boiler Hot Water Present {}"],
        gw.vars.DATA_SLAVE_CONTROL_TYPE: [None, "Boiler Control Type {}"],
        gw.vars.DATA_SLAVE_COOLING_SUPPORTED: [
            None, "Boiler Cooling Support {}"],
        gw.vars.DATA_SLAVE_DHW_CONFIG: [
            None, "Boiler Hot Water Configuration {}"],
        gw.vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: [
            None, "Boiler Pump Commands Support {}"],
        gw.vars.DATA_SLAVE_CH2_PRESENT: [
            None, "Boiler Central Heating 2 Present {}"],
        gw.vars.DATA_SLAVE_SERVICE_REQ: [
            DEVICE_CLASS_PROBLEM, "Boiler Service Required {}"],
        gw.vars.DATA_SLAVE_REMOTE_RESET: [
            None, "Boiler Remote Reset Support {}"],
        gw.vars.DATA_SLAVE_LOW_WATER_PRESS: [
            DEVICE_CLASS_PROBLEM, "Boiler Low Water Pressure {}"],
        gw.vars.DATA_SLAVE_GAS_FAULT: [
            DEVICE_CLASS_PROBLEM, "Boiler Gas Fault {}"],
        gw.vars.DATA_SLAVE_AIR_PRESS_FAULT: [
            DEVICE_CLASS_PROBLEM, "Boiler Air Pressure Fault {}"],
        gw.vars.DATA_SLAVE_WATER_OVERTEMP: [
            DEVICE_CLASS_PROBLEM, "Boiler Water Overtemperature {}"],
        gw.vars.DATA_REMOTE_TRANSFER_DHW: [
            None, "Remote Hot Water Setpoint Transfer Support {}"],
        gw.vars.DATA_REMOTE_TRANSFER_MAX_CH: [
            None, "Remote Maximum Central Heating Setpoint Write Support {}"],
        gw.vars.DATA_REMOTE_RW_DHW: [
            None, "Remote Hot Water Setpoint Write Support {}"],
        gw.vars.DATA_REMOTE_RW_MAX_CH: [
            None, "Remote Central Heating Setpoint Write Support {}"],
        gw.vars.DATA_ROVRD_MAN_PRIO: [
            None, "Remote Override Manual Change Priority {}"],
        gw.vars.DATA_ROVRD_AUTO_PRIO: [
            None, "Remote Override Program Change Priority {}"],
        gw.vars.OTGW_GPIO_A_STATE: [None, "Gateway GPIO A State {}"],
        gw.vars.OTGW_GPIO_B_STATE: [None, "Gateway GPIO B State {}"],
        gw.vars.OTGW_IGNORE_TRANSITIONS: [
            None, "Gateway Ignore Transitions {}"],
        gw.vars.OTGW_OVRD_HB: [None, "Gateway Override High Byte {}"],
    }
    sensors = []
    for var in gw.binary_sensors:
        device_class = sensor_info[var][0]
        friendly_name_format = sensor_info[var][1].format(gw.gw_id)
        sensors.append(OpenThermBinarySensor(gw, var, device_class,
                                             friendly_name_format))
    async_add_entities(sensors)


class OpenThermBinarySensor(BinarySensorDevice):
    """Represent an OpenTherm Gateway binary sensor."""

    def __init__(self, gw, var, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, '{}_{}'.format(var, gw.gw_id), hass=gw.hass)
        self._gateway = gw
        self._var = var
        self._state = None
        self._device_class = device_class
        self._friendly_name = friendly_name_format.format(gw.gw_id)

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug(
            "Added OpenTherm Gateway binary sensor %s", self._friendly_name)
        async_dispatcher_connect(self.hass, self._gateway.update_signal,
                                 self.receive_report)

    async def receive_report(self, status):
        """Handle status updates from the component."""
        self._state = bool(status.get(self._var))
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
        return self._friendly_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class

    @property
    def should_poll(self):
        """Return False because entity pushes its state."""
        return False
