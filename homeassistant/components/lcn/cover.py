"""Support for LCN covers."""
from homeassistant.components.cover import CoverDevice
from homeassistant.const import CONF_ADDRESS

from . import LcnDevice, get_connection
from .const import CONF_CONNECTIONS, CONF_MOTOR, DATA_LCN

DEPENDENCIES = ['lcn']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Setups the LCN cover platform."""
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

        devices.append(LcnCover(config, address_connection))

    async_add_entities(devices)


class LcnCover(LcnDevice, CoverDevice):
    """Representation of a LCN cover."""

    def __init__(self, config, address_connection):
        """Initialize the LCN cover."""
        super().__init__(config, address_connection)

        self.motor = self.pypck.lcn_defs.MotorPort[config[CONF_MOTOR]]
        self.motor_port_onoff = self.motor.value * 2
        self.motor_port_updown = self.motor_port_onoff + 1

        self._closed = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.hass.async_create_task(
            self.address_connection.activate_status_request_handler(
                self.motor))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._closed = True
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.DOWN
        self.address_connection.control_motors(states)
        await self.async_update_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._closed = False
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.UP
        self.address_connection.control_motors(states)
        await self.async_update_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._closed = None
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.STOP
        self.address_connection.control_motors(states)
        await self.async_update_ha_state()

    def input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if not isinstance(input_obj, self.pypck.inputs.ModStatusRelays):
            return

        states = input_obj.states  # list of boolean values (relay on/off)
        if states[self.motor_port_onoff]:  # motor is on
            self._closed = states[self.motor_port_updown]  # set direction

        self.async_schedule_update_ha_state()
