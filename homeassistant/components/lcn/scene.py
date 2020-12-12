"""Support for LCN scenes."""
from typing import Any

import pypck

from homeassistant.components.scene import Scene
from homeassistant.const import CONF_ADDRESS

from . import LcnEntity
from .const import (
    CONF_CONNECTIONS,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_SCENE,
    CONF_TRANSITION,
    DATA_LCN,
    OUTPUT_PORTS,
)
from .helpers import get_connection

PARALLEL_UPDATES = 0


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN scene platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        devices.append(LcnScene(config, address_connection))

    async_add_entities(devices)


class LcnScene(LcnEntity, Scene):
    """Representation of a LCN scene."""

    def __init__(self, config, device_connection):
        """Initialize the LCN scene."""
        super().__init__(config, device_connection)

        self.register_id = config[CONF_REGISTER]
        self.scene_id = config[CONF_SCENE]
        self.output_ports = []
        self.relay_ports = []

        for port in config[CONF_OUTPUTS]:
            if port in OUTPUT_PORTS:
                self.output_ports.append(pypck.lcn_defs.OutputPort[port])
            else:  # in RELEAY_PORTS
                self.relay_ports.append(pypck.lcn_defs.RelayPort[port])

        if config[CONF_TRANSITION] is None:
            self.transition = None
        else:
            self.transition = pypck.lcn_defs.time_to_ramp_value(config[CONF_TRANSITION])

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        await self.device_connection.activate_scene(
            self.register_id,
            self.scene_id,
            self.output_ports,
            self.relay_ports,
            self.transition,
        )
