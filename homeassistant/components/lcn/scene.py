"""Support for LCN scenes."""

import pypck

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE, Scene
from homeassistant.const import CONF_ADDRESS, CONF_DOMAIN, CONF_ENTITIES, CONF_SCENE

from . import LcnEntity
from .const import (
    CONF_DOMAIN_DATA,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_TRANSITION,
    OUTPUT_PORTS,
)
from .helpers import get_device_connection

PARALLEL_UPDATES = 0


def create_lcn_scene_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    device_connection = get_device_connection(
        hass, tuple(entity_config[CONF_ADDRESS]), config_entry
    )

    return LcnScene(entity_config, config_entry.entry_id, device_connection)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_SCENE:
            entities.append(create_lcn_scene_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnScene(LcnEntity, Scene):
    """Representation of a LCN scene."""

    def __init__(self, config, entry_id, device_connection):
        """Initialize the LCN scene."""
        super().__init__(config, entry_id, device_connection)

        self.register_id = config[CONF_DOMAIN_DATA][CONF_REGISTER]
        self.scene_id = config[CONF_DOMAIN_DATA][CONF_SCENE]
        self.output_ports = []
        self.relay_ports = []

        for port in config[CONF_DOMAIN_DATA][CONF_OUTPUTS]:
            if port in OUTPUT_PORTS:
                self.output_ports.append(pypck.lcn_defs.OutputPort[port])
            else:  # in RELEAY_PORTS
                self.relay_ports.append(pypck.lcn_defs.RelayPort[port])

        if config[CONF_DOMAIN_DATA][CONF_TRANSITION] is None:
            self.transition = None
        else:
            self.transition = pypck.lcn_defs.time_to_ramp_value(
                config[CONF_DOMAIN_DATA][CONF_TRANSITION]
            )

    async def async_activate(self, **kwargs):
        """Activate scene."""
        await self.device_connection.activate_scene(
            self.register_id,
            self.scene_id,
            self.output_ports,
            self.relay_ports,
            self.transition,
        )
