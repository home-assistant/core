"""Support for LCN sensors."""
from homeassistant.const import CONF_ADDRESS, CONF_UNIT_OF_MEASUREMENT

from . import LcnDevice, get_connection
from .const import (
    CONF_CONNECTIONS, CONF_SOURCE, DATA_LCN, LED_PORTS, S0_INPUTS, SETPOINTS,
    THRESHOLDS, VARIABLES)


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN sensor platform."""
    if discovery_info is None:
        return

    import pypck

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        if config[CONF_SOURCE] in VARIABLES + SETPOINTS + THRESHOLDS + \
                S0_INPUTS:
            device = LcnVariableSensor(config, address_connection)
        else:  # in LED_PORTS + LOGICOP_PORTS
            device = LcnLedLogicSensor(config, address_connection)

        devices.append(device)

    async_add_entities(devices)


class LcnVariableSensor(LcnDevice):
    """Representation of a LCN sensor for variables."""

    def __init__(self, config, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, address_connection)

        self.variable = self.pypck.lcn_defs.Var[config[CONF_SOURCE]]
        self.unit = self.pypck.lcn_defs.VarUnit.parse(
            config[CONF_UNIT_OF_MEASUREMENT])

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.hass.async_create_task(
            self.address_connection.activate_status_request_handler(
                self.variable))

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit.value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, self.pypck.inputs.ModStatusVar) or \
                input_obj.get_var() != self.variable:
            return

        self._value = (input_obj.get_value().to_var_unit(self.unit))
        self.async_schedule_update_ha_state()


class LcnLedLogicSensor(LcnDevice):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(self, config, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, address_connection)

        if config[CONF_SOURCE] in LED_PORTS:
            self.source = self.pypck.lcn_defs.LedPort[config[CONF_SOURCE]]
        else:
            self.source = self.pypck.lcn_defs.LogicOpPort[config[CONF_SOURCE]]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.hass.async_create_task(
            self.address_connection.activate_status_request_handler(
                self.source))

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj,
                          self.pypck.inputs.ModStatusLedsAndLogicOps):
            return

        if self.source in self.pypck.lcn_defs.LedPort:
            self._value = input_obj.get_led_state(
                self.source.value).name.lower()
        elif self.source in self.pypck.lcn_defs.LogicOpPort:
            self._value = input_obj.get_logic_op_state(
                self.source.value).name.lower()

        self.async_schedule_update_ha_state()
