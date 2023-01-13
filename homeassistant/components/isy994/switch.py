"""Support for ISY switches."""
from __future__ import annotations

from typing import Any

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_GROUP

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN
from .entity import ISYNodeEntity, ISYProgramEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY switch platform."""
    isy_data = hass.data[DOMAIN][entry.entry_id]
    entities: list[ISYSwitchProgramEntity | ISYSwitchEntity] = []
    devices: dict[str, DeviceInfo] = isy_data.devices
    for node in isy_data.nodes[Platform.SWITCH]:
        primary = node.primary_node
        if node.protocol == PROTO_GROUP and len(node.controllers) == 1:
            # If Group has only 1 Controller, link to that device instead of the hub
            primary = node.isy.nodes.get_by_id(node.controllers[0]).primary_node

        entities.append(ISYSwitchEntity(node, devices.get(primary)))

    for name, status, actions in isy_data.programs[Platform.SWITCH]:
        entities.append(ISYSwitchProgramEntity(name, status, actions))

    async_add_entities(entities)


class ISYSwitchEntity(ISYNodeEntity, SwitchEntity):
    """Representation of an ISY switch device."""

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY device is in the on state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch."""
        if not await self._node.turn_off():
            _LOGGER.debug("Unable to turn off switch")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch."""
        if not await self._node.turn_on():
            _LOGGER.debug("Unable to turn on switch")

    @property
    def icon(self) -> str | None:
        """Get the icon for groups."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            return "mdi:google-circles-communities"  # Matches isy scene icon
        return super().icon


class ISYSwitchProgramEntity(ISYProgramEntity, SwitchEntity):
    """A representation of an ISY program switch."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY switch program is on."""
        return bool(self._node.status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to turn on switch")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to turn off switch")

    @property
    def icon(self) -> str:
        """Get the icon for programs."""
        return "mdi:script-text-outline"  # Matches isy program icon
