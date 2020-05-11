"""Support for ISY994 covers."""
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.cover import DOMAIN as COVER, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNKNOWN
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    UOM_TO_STATES,
)
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 cover platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][COVER]:
        devices.append(ISYCoverEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][COVER]:
        devices.append(ISYCoverProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, COVER, devices)
    async_add_entities(devices)


class ISYCoverEntity(ISYNodeEntity, CoverEntity):
    """Representation of an ISY994 cover device."""

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        if self.value in [None, ISY_VALUE_UNKNOWN]:
            return STATE_UNKNOWN
        return sorted((0, self.value, 100))[1]

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY994 cover device is closed."""
        return self.state == STATE_CLOSED

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return UOM_TO_STATES["97"].get(self.value, STATE_OPEN)

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover device."""
        if not self._node.turn_on(val=100):
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover device."""
        if not self._node.turn_off():
            _LOGGER.error("Unable to close the cover")


class ISYCoverProgramEntity(ISYProgramEntity, CoverEntity):
    """Representation of an ISY994 cover program."""

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover program."""
        return STATE_CLOSED if bool(self.value) else STATE_OPEN

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover program."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover program."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to close the cover")
