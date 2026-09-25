"""Cover platform for the Profalux Neosol integration."""

from typing import Any, override

from pyneosol import Action, NeosolError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NeosolConfigEntry
from .entity import NeosolEntity

# One serial link, one AT command at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeosolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the shutters exposed by the dongle."""
    coordinator = entry.runtime_data
    # Only the channels read at setup become shutters: one paired afterwards shows up
    # once the entry is reloaded.
    async_add_entities(
        NeosolCover(coordinator, channel) for channel in sorted(coordinator.data)
    )


class NeosolCover(NeosolEntity, CoverEntity):
    """A roller shutter driven by one channel of the dongle."""

    # The radio link is one way: a sent frame is never acknowledged and no position can
    # be read back, so whether a shutter is open is simply unknown, and stays that way.
    # Reporting what the last command implied would be a guess the shutter never
    # confirmed, and a shutter driven from its own remote would make it wrong.
    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_is_closed: bool | None = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    async def _async_send(self, action: Action) -> None:
        """Transmit ``action`` on this channel."""
        try:
            await self.coordinator.dongle.send(self.channel, action)
        except NeosolError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_failed",
                translation_placeholders={
                    "channel": str(self.channel),
                    "error": str(err),
                },
            ) from err

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shutter."""
        await self._async_send(Action.OPEN)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shutter."""
        await self._async_send(Action.CLOSE)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the shutter mid-travel."""
        await self._async_send(Action.STOP)
