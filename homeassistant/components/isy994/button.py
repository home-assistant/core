"""Representation of ISY/IoX buttons."""
from __future__ import annotations

from pyisy import ISY
from pyisy.constants import PROTO_INSTEON, PROTO_NETWORK_RESOURCE
from pyisy.nodes import Node

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _async_isy_to_configuration_url
from .const import (
    DOMAIN as ISY994_DOMAIN,
    ISY994_ISY,
    ISY994_NODES,
    ISY_CONF_FIRMWARE,
    ISY_CONF_MODEL,
    ISY_CONF_NAME,
    ISY_CONF_NETWORKING,
    ISY_CONF_UUID,
    MANUFACTURER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX button from config entry."""
    hass_isy_data = hass.data[ISY994_DOMAIN][config_entry.entry_id]
    isy: ISY = hass_isy_data[ISY994_ISY]
    uuid = isy.configuration[ISY_CONF_UUID]
    entities: list[
        ISYNodeQueryButtonEntity
        | ISYNodeBeepButtonEntity
        | ISYNetworkResourceButtonEntity
    ] = []
    nodes: dict = hass_isy_data[ISY994_NODES]
    for node in nodes[Platform.BUTTON]:
        entities.append(ISYNodeQueryButtonEntity(node, f"{uuid}_{node.address}"))
        if node.protocol == PROTO_INSTEON:
            entities.append(ISYNodeBeepButtonEntity(node, f"{uuid}_{node.address}"))

    for node in nodes[PROTO_NETWORK_RESOURCE]:
        entities.append(
            ISYNetworkResourceButtonEntity(node, f"{uuid}_{PROTO_NETWORK_RESOURCE}")
        )

    # Add entity to query full system
    entities.append(ISYNodeQueryButtonEntity(isy, uuid))

    async_add_entities(entities)


class ISYNodeQueryButtonEntity(ButtonEntity):
    """Representation of a device query button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, node: Node | ISY, base_unique_id: str) -> None:
        """Initialize a query ISY device button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = "Query"
        self._attr_unique_id = f"{base_unique_id}_query"
        self._attr_device_info = DeviceInfo(
            identifiers={(ISY994_DOMAIN, base_unique_id)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.query()


class ISYNodeBeepButtonEntity(ButtonEntity):
    """Representation of a device beep button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, node: Node, base_unique_id: str) -> None:
        """Initialize a beep Insteon device button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = "Beep"
        self._attr_unique_id = f"{base_unique_id}_beep"
        self._attr_device_info = DeviceInfo(
            identifiers={(ISY994_DOMAIN, base_unique_id)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.beep()


class ISYNetworkResourceButtonEntity(ButtonEntity):
    """Representation of an ISY/IoX Network Resource button entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, node: Node, base_unique_id: str) -> None:
        """Initialize an ISY network resource button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = node.name
        self._attr_unique_id = f"{base_unique_id}_{node.address}"
        url = _async_isy_to_configuration_url(node.isy)
        config = node.isy.configuration
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    ISY994_DOMAIN,
                    f"{config[ISY_CONF_UUID]}_{PROTO_NETWORK_RESOURCE}",
                )
            },
            manufacturer=MANUFACTURER,
            name=f"{config[ISY_CONF_NAME]} {ISY_CONF_NETWORKING}",
            model=config[ISY_CONF_MODEL],
            sw_version=config[ISY_CONF_FIRMWARE],
            configuration_url=url,
            via_device=(ISY994_DOMAIN, config[ISY_CONF_UUID]),
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.run()
