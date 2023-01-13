"""Representation of ISY/IoX buttons."""
from __future__ import annotations

from pyisy import ISY
from pyisy.constants import PROTO_INSTEON
from pyisy.networking import NetworkCommand
from pyisy.nodes import Node

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NETWORK, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX button from config entry."""
    isy_data = hass.data[DOMAIN][config_entry.entry_id]
    isy: ISY = isy_data.root
    device_info = isy_data.devices
    entities: list[
        ISYNodeQueryButtonEntity
        | ISYNodeBeepButtonEntity
        | ISYNetworkResourceButtonEntity
    ] = []

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

    for node in isy_data.net_resources:
        entities.append(
            ISYNetworkResourceButtonEntity(
                node=node,
                name=node.name,
                unique_id=isy_data.uid_base(node),
                device_info=device_info[CONF_NETWORK],
            )
        )

    # Add entity to query full system
    entities.append(
        ISYNodeQueryButtonEntity(
            node=isy,
            name="Query",
            unique_id=isy.uuid,
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
