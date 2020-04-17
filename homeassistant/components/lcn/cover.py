"""Support for LCN covers."""
import pypck

from homeassistant.components.cover import CoverDevice
from homeassistant.const import CONF_ADDRESS

from . import LcnDevice
from .const import CONF_CONNECTIONS, CONF_MOTOR, CONF_REVERSE_TIME, DATA_LCN
from .helpers import get_connection


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Setups the LCN cover platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        if config[CONF_MOTOR] == "OUTPUTS":
            devices.append(LcnOutputsCover(config, address_connection))
        else:  # RELAYS
            devices.append(LcnRelayCover(config, address_connection))

    async_add_entities(devices)


class LcnOutputsCover(LcnDevice, CoverDevice):
    """Representation of a LCN cover connected to output ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN cover."""
        super().__init__(config, address_connection)

        self.output_ids = [
            pypck.lcn_defs.OutputPort["OUTPUTUP"].value,
            pypck.lcn_defs.OutputPort["OUTPUTDOWN"].value,
        ]
        if CONF_REVERSE_TIME in config:
            self.reverse_time = pypck.lcn_defs.MotorReverseTime[
                config[CONF_REVERSE_TIME]
            ]
        else:
            self.reverse_time = None
        self._closed = None
        self.state_up = False
        self.state_down = False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(
            pypck.lcn_defs.OutputPort["OUTPUTUP"]
        )
        await self.address_connection.activate_status_request_handler(
            pypck.lcn_defs.OutputPort["OUTPUTDOWN"]
        )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._closed = True

        state = pypck.lcn_defs.MotorStateModifier.DOWN
        self.address_connection.control_motors_outputs(state)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._closed = False
        state = pypck.lcn_defs.MotorStateModifier.UP
        self.address_connection.control_motors_outputs(state, self.reverse_time)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._closed = None
        state = pypck.lcn_defs.MotorStateModifier.STOP
        self.address_connection.control_motors_outputs(state, self.reverse_time)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() not in self.output_ids
        ):
            return

        if input_obj.get_output_id() == self.output_ids[0]:
            self.state_up = input_obj.get_percent() > 0
        else:  # self.output_ids[1]
            self.state_down = input_obj.get_percent() > 0

        if self.state_up and not self.state_down:
            self._closed = False  # Cover open
        elif self.state_down and not self.state_up:
            self._closed = True  # Cover closed

        self.async_write_ha_state()


class LcnRelayCover(LcnDevice, CoverDevice):
    """Representation of a LCN cover connected to relays."""

    def __init__(self, config, address_connection):
        """Initialize the LCN cover."""
        super().__init__(config, address_connection)

        self.motor = pypck.lcn_defs.MotorPort[config[CONF_MOTOR]]
        self.motor_port_onoff = self.motor.value * 2
        self.motor_port_updown = self.motor_port_onoff + 1

        self._closed = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(self.motor)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._closed = True
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.DOWN
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._closed = False
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.UP
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._closed = None
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.STOP
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        states = input_obj.states  # list of boolean values (relay on/off)
        if states[self.motor_port_onoff]:  # motor is on
            self._closed = states[self.motor_port_updown]  # set direction

        self.async_write_ha_state()
