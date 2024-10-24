"""Support for Vemmio switches."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VemmioEntity
from .const import CONF_REVISION, DOMAIN, LOGGER
from .coordinator import VemmioData, VemmioDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vemmio switches."""

    coordinator: VemmioDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    typ = entry.data[CONF_TYPE]
    revision = entry.data[CONF_REVISION]
    key = "switch"

    nodes = [node for node in coordinator.data.nodes if key in node.capabilities]

    async_add_entities(
        VemmioSwitchEntity(
            coordinator=coordinator,
            mac=mac,
            typ=typ,
            revision=revision,
            node=node,
            key=key,
            index=index + 1,
        )
        for index, node in enumerate(nodes)
    )


class VemmioSwitchEntity(VemmioEntity, SwitchEntity):
    """Vemmio switch entity."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        data: VemmioData = self.coordinator.data
        state: bool = data.is_on(self.node.uuid)
        LOGGER.debug("switch state: %s", state)
        return state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        LOGGER.debug("switch: turn on")
        await self.client().turn_on(self.node.uuid)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        LOGGER.debug("switch: turn off")
        await self.client().turn_off(self.node.uuid)
