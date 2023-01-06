"""Representation of ISY/IoX buttons."""
from __future__ import annotations

from pyisy import ISY
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
    entities: list[ISYNodeQueryButtonEntity | ISYSystemQueryButtonEntity] = []
    for node in hass_isy_data[ISY994_NODES][Platform.BUTTON]:
        entities.append(ISYNodeQueryButtonEntity(node))

    entities.append(ISYSystemQueryButtonEntity(hass_isy_data[ISY994_ISY]))

    async_add_entities(entities)


class ISYNodeQueryButtonEntity(ButtonEntity):
    """Representation of a device query button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, node: Node) -> None:
        """Initialize a query ISY device button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = "Query"
        base_unique_id: str = (
            f"{self._node.isy.configuration['uuid']}_{self._node.address}"
        )
        self._attr_unique_id = f"{base_unique_id}_query"
        self._attr_device_info = DeviceInfo(
            identifiers={(ISY994_DOMAIN, base_unique_id)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        self.hass.async_create_task(self._node.query())


class ISYSystemQueryButtonEntity(ButtonEntity):
    """Representation of a system query button entity."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, isy: ISY) -> None:
        """Initialize a query ISY system button entity."""
        self._isy = isy

        # Entity class attributes
        self._attr_name = "Query"
        base_unique_id: str = f"{self._isy.configuration['uuid']}"
        self._attr_unique_id = f"{base_unique_id}_query"
        self._attr_device_info = DeviceInfo(
            identifiers={(ISY994_DOMAIN, base_unique_id)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        self.hass.async_create_task(self._isy.query())
