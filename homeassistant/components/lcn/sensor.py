"""Support for LCN sensors."""
import pypck

from homeassistant.const import CONF_ADDRESS, CONF_SOURCE, CONF_UNIT_OF_MEASUREMENT

from . import LcnEntity
from .const import (
    CONF_CONNECTIONS,
    DATA_LCN,
    LED_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VARIABLES,
)
from .helpers import get_connection


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        device_connection = connection.get_address_conn(addr)

        if config[CONF_SOURCE] in VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS:
            device = LcnVariableSensor(config, device_connection)
        else:  # in LED_PORTS + LOGICOP_PORTS
            device = LcnLedLogicSensor(config, device_connection)

        devices.append(device)

    async_add_entities(devices)


class LcnVariableSensor(LcnEntity):
    """Representation of a LCN sensor for variables."""

    def __init__(self, config, device_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, device_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_SOURCE]]
        self.unit = pypck.lcn_defs.VarUnit.parse(config[CONF_UNIT_OF_MEASUREMENT])

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.variable)

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
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.variable
        ):
            return

        self._value = input_obj.get_value().to_var_unit(self.unit)
        self.async_write_ha_state()


class LcnLedLogicSensor(LcnEntity):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(self, config, device_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, device_connection)

        if config[CONF_SOURCE] in LED_PORTS:
            self.source = pypck.lcn_defs.LedPort[config[CONF_SOURCE]]
        else:
            self.source = pypck.lcn_defs.LogicOpPort[config[CONF_SOURCE]]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.source)

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusLedsAndLogicOps):
            return

        if self.source in pypck.lcn_defs.LedPort:
            self._value = input_obj.get_led_state(self.source.value).name.lower()
        elif self.source in pypck.lcn_defs.LogicOpPort:
            self._value = input_obj.get_logic_op_state(self.source.value).name.lower()

        self.async_write_ha_state()
