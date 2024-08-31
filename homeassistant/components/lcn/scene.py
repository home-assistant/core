"""Support for LCN scenes."""

from collections.abc import Iterable
from functools import partial
from typing import Any

import pypck

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_DOMAIN, CONF_ENTITIES, CONF_SCENE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import LcnEntity
from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_TRANSITION,
    DOMAIN,
    OUTPUT_PORTS,
)
from .helpers import DeviceConnectionType, get_device_connection

PARALLEL_UPDATES = 0


def add_lcn_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities: list[LcnScene] = []
    for entity_config in entity_configs:
        device_connection = get_device_connection(
            hass, entity_config[CONF_ADDRESS], config_entry
        )

        entities.append(
            LcnScene(entity_config, config_entry.entry_id, device_connection)
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        hass,
        config_entry,
        async_add_entities,
    )

    hass.data[DOMAIN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS].update(
        {DOMAIN_SCENE: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_SCENE
        ),
    )


class LcnScene(LcnEntity, Scene):
    """Representation of a LCN scene."""

    def __init__(
        self, config: ConfigType, entry_id: str, device_connection: DeviceConnectionType
    ) -> None:
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

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        await self.device_connection.activate_scene(
            self.register_id,
            self.scene_id,
            self.output_ports,
            self.relay_ports,
            self.transition,
        )
