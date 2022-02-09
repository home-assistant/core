"""Representation of Z-Wave buttons."""
from __future__ import annotations

import logging

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .helpers import get_device_id

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_ping_button_entity(node: ZwaveNode) -> None:
        """Add ping button entity."""
        async_add_entities([ZWaveNodePingButton(config_entry, client, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_ping_button_entity",
            async_add_ping_button_entity,
        )
    )


class ZWaveNodePingButton(ButtonEntity):
    """Representation of a ping button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, node: ZwaveNode
    ) -> None:
        """Initialize a ping Z-Wave device button entity."""
        self.config_entry = config_entry
        self.client = client
        self.node = node
        name: str = (
            self.node.name
            or self.node.device_config.description
            or f"Node {self.node.node_id}"
        )
        # Entity class attributes
        self._attr_name = f"{name}: Ping Node"
        self._attr_unique_id = (
            f"{self.client.driver.controller.home_id}.{node.node_id}.ping_node"
        )
        # device is precreated in main handler
        self._attr_device_info = DeviceInfo(
            identifiers={get_device_id(self.client, self.node)},
        )

    async def async_press(self) -> None:
        """Press the button."""
        self.hass.async_create_task(self.node.async_ping())
