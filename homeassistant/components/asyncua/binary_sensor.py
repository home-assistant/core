"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Union

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AsyncuaCoordinator
from .const import (
    CONF_NODE_DEVICE_CLASS,
    CONF_NODE_HUB,
    CONF_NODE_ID,
    CONF_NODE_NAME,
    CONF_NODE_UNIQUE_ID,
    CONF_NODES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

NODE_SCHEMA = {
    CONF_NODES: [
        {
            vol.Optional(CONF_NODE_DEVICE_CLASS): cv.string,
            vol.Optional(CONF_NODE_UNIQUE_ID): cv.string,
            vol.Required(CONF_NODE_ID): cv.string,
            vol.Required(CONF_NODE_NAME): cv.string,
            vol.Required(CONF_NODE_HUB): cv.string,
        }
    ]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    schema=NODE_SCHEMA,
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up asyncua_binary_sensor coordinator_nodes."""

    # {"hub": [node0, node1]}
    # where node0 equals {"name": "node0", "unique_id": "node0", ...}.
    coordinator_nodes: dict[str, list[dict[str, str]]] = {}
    coordinators: dict[str, AsyncuaCoordinator] = {}
    asyncua_sensors: list = []

    # Compile coordinators with respective nodes
    for _idx_node, val_node in enumerate(config[CONF_NODES]):
        if val_node[CONF_NODE_HUB] not in coordinator_nodes.keys():
            coordinator_nodes[val_node[CONF_NODE_HUB]] = []
        coordinator_nodes[val_node[CONF_NODE_HUB]].append(val_node)

    # Compile dictionary of {hub: [node0, node1, ...]}
    for key_coordinator, val_coordinator in coordinator_nodes.items():
        # Get the respective asyncua coordinator
        if key_coordinator not in hass.data[DOMAIN].keys():
            raise ConfigEntryError(
                f"Asyncua hub {key_coordinator} not found. Specify a valid asyncua hub in the configuration."
            )
        coordinators[key_coordinator] = hass.data[DOMAIN][key_coordinator]
        coordinators[key_coordinator].add_sensors(sensors=val_coordinator)

        # Create sensors with injecting respective asyncua coordinator
        for _idx_sensor, val_sensor in enumerate(val_coordinator):
            asyncua_sensors.append(
                AsyncuaBinarySensor(
                    coordinator=coordinators[key_coordinator],
                    name=val_sensor[CONF_NODE_NAME],
                    unique_id=val_sensor.get(CONF_NODE_UNIQUE_ID),
                    hub=val_sensor[CONF_NODE_HUB],
                    node_id=val_sensor[CONF_NODE_ID],
                    device_class=val_sensor.get(CONF_NODE_DEVICE_CLASS),
                )
            )
    async_add_entities(new_entities=asyncua_sensors)


class AsyncuaBinarySensor(CoordinatorEntity[AsyncuaCoordinator], BinarySensorEntity):
    """A binary sensor implementation for Asyncua OPCUA nodes."""

    def __init__(
        self,
        coordinator: AsyncuaCoordinator,
        name: str,
        hub: str,
        node_id: str,
        device_class: Any,
        unique_id: Union[str, None] = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator)
        self._attr_name = name
        self._attr_unique_id = (
            unique_id if unique_id is not None else f"{DOMAIN}.{hub}.{node_id}"
        )
        self._attr_available = False
        self._attr_device_class = device_class
        self._attr_is_on: bool | None = None
        self._attr_state: None = None
        self._hub = hub
        self._node_id = node_id

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        self._attr_is_on = self._parse_coordinator_data(
            coordinator_data=self.coordinator.data
        )
        return self._attr_is_on

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the sensor."""
        return self._attr_unique_id

    @property
    def node_id(self) -> str:
        """Return the node address provided by the OPCUA server."""
        return self._node_id

    def _parse_coordinator_data(
        self,
        coordinator_data: dict[str, Any],
    ) -> Any:
        """Parse the value from the mapped coordinator."""
        if self._attr_name is None:
            raise ConfigEntryError(
                f"Unable to find {self._attr_name} in coordinator {self.coordinator.name}"
            )
        return coordinator_data.get(self._attr_name)
