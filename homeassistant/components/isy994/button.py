"""Representation of ISY/IoX buttons."""
from __future__ import annotations

from pyisy import ISY
from pyisy.constants import PROTO_INSTEON
from pyisy.nodes import Node

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ISY994_DOMAIN, ISY994_ISY, ISY994_NODES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX button from config entry."""
    hass_isy_data = hass.data[ISY994_DOMAIN][config_entry.entry_id]
    isy: ISY = hass_isy_data[ISY994_ISY]
    uuid = isy.configuration["uuid"]
    entities: list[ISYNodeQueryButtonEntity | ISYNodeBeepButtonEntity] = []
    for node in hass_isy_data[ISY994_NODES][Platform.BUTTON]:
        entities.append(ISYNodeQueryButtonEntity(node, f"{uuid}_{node.address}"))
        if node.protocol == PROTO_INSTEON:
            entities.append(ISYNodeBeepButtonEntity(node, f"{uuid}_{node.address}"))

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
