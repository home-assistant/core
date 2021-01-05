"""Support for LCN switches."""
import pypck

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_ADDRESS

from . import LcnEntity
from .const import CONF_CONNECTIONS, CONF_OUTPUT, DATA_LCN, OUTPUT_PORTS
from .helpers import get_connection

PARALLEL_UPDATES = 0


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN switch platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        if config[CONF_OUTPUT] in OUTPUT_PORTS:
            device = LcnOutputSwitch(config, address_connection)
        else:  # in RELAY_PORTS
            device = LcnRelaySwitch(config, address_connection)

        devices.append(device)

    async_add_entities(devices)


class LcnOutputSwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for output ports."""

    def __init__(self, config, device_connection):
        """Initialize the LCN switch."""
        super().__init__(config, device_connection)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_OUTPUT]]

        self._is_on = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.output)

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        if not await self.device_connection.dim_output(self.output.value, 100, 0):
            return
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        if not await self.device_connection.dim_output(self.output.value, 0, 0):
            return
        self._is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() != self.output.value
        ):
            return

        self._is_on = input_obj.get_percent() > 0
        self.async_write_ha_state()


class LcnRelaySwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for relay ports."""

    def __init__(self, config, device_connection):
        """Initialize the LCN switch."""
        super().__init__(config, device_connection)

        self.output = pypck.lcn_defs.RelayPort[config[CONF_OUTPUT]]

        self._is_on = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.output)

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.ON
        if not await self.device_connection.control_relays(states):
            return
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""

        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.OFF
        if not await self.device_connection.control_relays(states):
            return
        self._is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        self._is_on = input_obj.get_state(self.output.value)
        self.async_write_ha_state()
