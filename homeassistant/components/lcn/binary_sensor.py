"""Support for LCN binary sensors."""
import pypck

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_ADDRESS

from . import LcnDevice
from .const import BINSENSOR_PORTS, CONF_CONNECTIONS, CONF_SOURCE, DATA_LCN, SETPOINTS
from .helpers import get_connection


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN binary sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        if config[CONF_SOURCE] in SETPOINTS:
            device = LcnRegulatorLockSensor(config, address_connection)
        elif config[CONF_SOURCE] in BINSENSOR_PORTS:
            device = LcnBinarySensor(config, address_connection)
        else:  # in KEYS
            device = LcnLockKeysSensor(config, address_connection)

        devices.append(device)

    async_add_entities(devices)


class LcnRegulatorLockSensor(LcnDevice, BinarySensorEntity):
    """Representation of a LCN binary sensor for regulator locks."""

    def __init__(self, config, address_connection):
        """Initialize the LCN binary sensor."""
        super().__init__(config, address_connection)

        self.setpoint_variable = pypck.lcn_defs.Var[config[CONF_SOURCE]]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(
            self.setpoint_variable
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.setpoint_variable
        ):
            return

        self._value = input_obj.get_value().is_locked_regulator()
        self.async_write_ha_state()


class LcnBinarySensor(LcnDevice, BinarySensorEntity):
    """Representation of a LCN binary sensor for binary sensor ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN binary sensor."""
        super().__init__(config, address_connection)

        self.bin_sensor_port = pypck.lcn_defs.BinSensorPort[config[CONF_SOURCE]]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(
            self.bin_sensor_port
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusBinSensors):
            return

        self._value = input_obj.get_state(self.bin_sensor_port.value)
        self.async_write_ha_state()


class LcnLockKeysSensor(LcnDevice, BinarySensorEntity):
    """Representation of a LCN sensor for key locks."""

    def __init__(self, config, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, address_connection)

        self.source = pypck.lcn_defs.Key[config[CONF_SOURCE]]
        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(self.source)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusKeyLocks)
            or self.source not in pypck.lcn_defs.Key
        ):
            return

        table_id = ord(self.source.name[0]) - 65
        key_id = int(self.source.name[1]) - 1

        self._value = input_obj.get_state(table_id, key_id)
        self.async_write_ha_state()
