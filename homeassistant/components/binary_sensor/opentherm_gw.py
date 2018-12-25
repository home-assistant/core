"""
Support for OpenTherm Gateway binary sensors.

For more details about this platform, please refer to the documentation at
http://home-assistant.io/components/binary_sensor.opentherm_gw/
"""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT)
from homeassistant.components.opentherm_gw import (
    DATA_GW_VARS, DATA_OPENTHERM_GW, SIGNAL_OPENTHERM_GW_UPDATE)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id

DEVICE_CLASS_COLD = 'cold'
DEVICE_CLASS_HEAT = 'heat'
DEVICE_CLASS_PROBLEM = 'problem'

DEPENDENCIES = ['opentherm_gw']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the OpenTherm Gateway binary sensors."""
    if discovery_info is None:
        return
    gw_vars = hass.data[DATA_OPENTHERM_GW][DATA_GW_VARS]
    sensor_info = {
        # [device_class, friendly_name]
        gw_vars.DATA_MASTER_CH_ENABLED: [
            None, "Thermostat Central Heating Enabled"],
        gw_vars.DATA_MASTER_DHW_ENABLED: [
            None, "Thermostat Hot Water Enabled"],
        gw_vars.DATA_MASTER_COOLING_ENABLED: [
            None, "Thermostat Cooling Enabled"],
        gw_vars.DATA_MASTER_OTC_ENABLED: [
            None, "Thermostat Outside Temperature Correction Enabled"],
        gw_vars.DATA_MASTER_CH2_ENABLED: [
            None, "Thermostat Central Heating 2 Enabled"],
        gw_vars.DATA_SLAVE_FAULT_IND: [
            DEVICE_CLASS_PROBLEM, "Boiler Fault Indication"],
        gw_vars.DATA_SLAVE_CH_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Central Heating Status"],
        gw_vars.DATA_SLAVE_DHW_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Hot Water Status"],
        gw_vars.DATA_SLAVE_FLAME_ON: [
            DEVICE_CLASS_HEAT, "Boiler Flame Status"],
        gw_vars.DATA_SLAVE_COOLING_ACTIVE: [
            DEVICE_CLASS_COLD, "Boiler Cooling Status"],
        gw_vars.DATA_SLAVE_CH2_ACTIVE: [
            DEVICE_CLASS_HEAT, "Boiler Central Heating 2 Status"],
        gw_vars.DATA_SLAVE_DIAG_IND: [
            DEVICE_CLASS_PROBLEM, "Boiler Diagnostics Indication"],
        gw_vars.DATA_SLAVE_DHW_PRESENT: [None, "Boiler Hot Water Present"],
        gw_vars.DATA_SLAVE_CONTROL_TYPE: [None, "Boiler Control Type"],
        gw_vars.DATA_SLAVE_COOLING_SUPPORTED: [None, "Boiler Cooling Support"],
        gw_vars.DATA_SLAVE_DHW_CONFIG: [
            None, "Boiler Hot Water Configuration"],
        gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: [
            None, "Boiler Pump Commands Support"],
        gw_vars.DATA_SLAVE_CH2_PRESENT: [
            None, "Boiler Central Heating 2 Present"],
        gw_vars.DATA_SLAVE_SERVICE_REQ: [
            DEVICE_CLASS_PROBLEM, "Boiler Service Required"],
        gw_vars.DATA_SLAVE_REMOTE_RESET: [None, "Boiler Remote Reset Support"],
        gw_vars.DATA_SLAVE_LOW_WATER_PRESS: [
            DEVICE_CLASS_PROBLEM, "Boiler Low Water Pressure"],
        gw_vars.DATA_SLAVE_GAS_FAULT: [
            DEVICE_CLASS_PROBLEM, "Boiler Gas Fault"],
        gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: [
            DEVICE_CLASS_PROBLEM, "Boiler Air Pressure Fault"],
        gw_vars.DATA_SLAVE_WATER_OVERTEMP: [
            DEVICE_CLASS_PROBLEM, "Boiler Water Overtemperature"],
        gw_vars.DATA_REMOTE_TRANSFER_DHW: [
            None, "Remote Hot Water Setpoint Transfer Support"],
        gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: [
            None, "Remote Maximum Central Heating Setpoint Write Support"],
        gw_vars.DATA_REMOTE_RW_DHW: [
            None, "Remote Hot Water Setpoint Write Support"],
        gw_vars.DATA_REMOTE_RW_MAX_CH: [
            None, "Remote Central Heating Setpoint Write Support"],
        gw_vars.DATA_ROVRD_MAN_PRIO: [
            None, "Remote Override Manual Change Priority"],
        gw_vars.DATA_ROVRD_AUTO_PRIO: [
            None, "Remote Override Program Change Priority"],
        gw_vars.OTGW_GPIO_A_STATE: [None, "Gateway GPIO A State"],
        gw_vars.OTGW_GPIO_B_STATE: [None, "Gateway GPIO B State"],
        gw_vars.OTGW_IGNORE_TRANSITIONS: [None, "Gateway Ignore Transitions"],
        gw_vars.OTGW_OVRD_HB: [None, "Gateway Override High Byte"],
    }
    sensors = []
    for var in discovery_info:
        device_class = sensor_info[var][0]
        friendly_name = sensor_info[var][1]
        entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, var, hass=hass)
        sensors.append(OpenThermBinarySensor(entity_id, var, device_class,
                                             friendly_name))
    async_add_entities(sensors)


class OpenThermBinarySensor(BinarySensorDevice):
    """Represent an OpenTherm Gateway binary sensor."""

    def __init__(self, entity_id, var, device_class, friendly_name):
        """Initialize the binary sensor."""
        self.entity_id = entity_id
        self._var = var
        self._state = None
        self._device_class = device_class
        self._friendly_name = friendly_name

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug(
            "Added OpenTherm Gateway binary sensor %s", self._friendly_name)
        async_dispatcher_connect(self.hass, SIGNAL_OPENTHERM_GW_UPDATE,
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
