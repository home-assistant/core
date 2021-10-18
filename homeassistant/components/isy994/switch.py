"""Support for ISY994 switches."""

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_GROUP

from homeassistant.components.switch import DOMAIN as SWITCH, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 switch platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][SWITCH]:
        devices.append(ISYSwitchEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][SWITCH]:
        devices.append(ISYSwitchProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, SWITCH, devices)
    async_add_entities(devices)


class ISYSwitchEntity(ISYNodeEntity, SwitchEntity):
    """Representation of an ISY994 switch device."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 device is in the on state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        if not await self._node.turn_off():
            _LOGGER.debug("Unable to turn off switch")

    async def async_turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch."""
        if not await self._node.turn_on():
            _LOGGER.debug("Unable to turn on switch")

    @property
    def icon(self) -> str:
        """Get the icon for groups."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            return "mdi:google-circles-communities"  # Matches isy scene icon
        return super().icon


class ISYSwitchProgramEntity(ISYProgramEntity, SwitchEntity):
    """A representation of an ISY994 program switch."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 switch program is on."""
        return bool(self._node.status)

    async def async_turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to turn on switch")

    async def async_turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to turn off switch")

    @property
    def icon(self) -> str:
        """Get the icon for programs."""
        return "mdi:script-text-outline"  # Matches isy program icon
