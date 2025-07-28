"""Representation of ISY/IoX buttons."""

from __future__ import annotations

from pyisy import ISY
from pyisy.constants import (
    ATTR_ACTION,
    NC_NODE_ENABLED,
    PROTO_INSTEON,
    TAG_ADDRESS,
    TAG_ENABLED,
)
from pyisy.helpers import EventListener, NodeProperty
from pyisy.networking import NetworkCommand
from pyisy.nodes import Node

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_NETWORK, DOMAIN
from .models import IsyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IsyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISY/IoX button from config entry."""
    isy_data = config_entry.runtime_data
    isy = isy_data.root
    device_info = isy_data.devices
    entities: list[
        ISYNodeQueryButtonEntity
        | ISYNodeBeepButtonEntity
        | ISYNetworkResourceButtonEntity
    ] = [
        ISYNetworkResourceButtonEntity(
            node=node,
            name=node.name,
            unique_id=isy_data.uid_base(node),
            device_info=device_info[CONF_NETWORK],
        )
        for node in isy_data.net_resources
    ]

    for node in isy_data.root_nodes[Platform.BUTTON]:
        entities.append(
            ISYNodeQueryButtonEntity(
                node=node,
                name="Query",
                unique_id=f"{isy_data.uid_base(node)}_query",
                entity_category=EntityCategory.DIAGNOSTIC,
                device_info=device_info[node.address],
            )
        )
        if node.protocol == PROTO_INSTEON:
            entities.append(
                ISYNodeBeepButtonEntity(
                    node=node,
                    name="Beep",
                    unique_id=f"{isy_data.uid_base(node)}_beep",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    device_info=device_info[node.address],
                )
            )

    # Add entity to query full system
    entities.append(
        ISYNodeQueryButtonEntity(
            node=isy,
            name="Query",
            unique_id=f"{isy.uuid}_query",
            device_info=DeviceInfo(identifiers={(DOMAIN, isy.uuid)}),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    )

    async_add_entities(entities)


class ISYNodeButtonEntity(ButtonEntity):
    """Representation of an ISY/IoX device button entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        node: Node | ISY | NetworkCommand,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize a query ISY device button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = name
        self._attr_entity_category = entity_category
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._node_enabled = getattr(node, TAG_ENABLED, True)
        self._availability_handler: EventListener | None = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._node_enabled

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        # No status for NetworkResources or ISY Query buttons
        if not hasattr(self._node, "status_events") or not hasattr(self._node, "isy"):
            return
        self._availability_handler = self._node.isy.nodes.status_events.subscribe(
            self.async_on_update,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NC_NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_update(self, event: NodeProperty, key: str) -> None:
        """Handle the update event from the ISY Node."""
        # Watch for node availability/enabled changes only
        self._node_enabled = getattr(self._node, TAG_ENABLED, True)
        self.async_write_ha_state()


class ISYNodeQueryButtonEntity(ISYNodeButtonEntity):
    """Representation of a device query button entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.query()


class ISYNodeBeepButtonEntity(ISYNodeButtonEntity):
    """Representation of a device beep button entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.beep()


class ISYNetworkResourceButtonEntity(ISYNodeButtonEntity):
    """Representation of an ISY/IoX Network Resource button entity."""

    _attr_has_entity_name = False

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.run()
