"""Support for Tellstick covers using Tellstick Net."""
from typing import Any

from homeassistant.components import cover
from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import tellduslive
from . import TelldusLiveClient
from .entry import TelldusLiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tellduslive sensors dynamically."""

    async def async_discover_cover(device_id):
        """Discover and add a discovered sensor."""
        client: TelldusLiveClient = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveCover(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(cover.DOMAIN, tellduslive.DOMAIN),
        async_discover_cover,
    )


class TelldusLiveCover(TelldusLiveEntity, CoverEntity):
    """Representation of a cover."""

    @property
    def is_closed(self) -> bool:
        """Return the current position of the cover."""
        return self.device.is_down

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.device.down()
        self._update_callback()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.device.up()
        self._update_callback()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self.device.stop()
        self._update_callback()
