"""Cover platform for Somfy RTS."""

from typing import Any

from rf_protocols import SomfyRTSButton

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import SomfyRTSConfigEntry, SomfyRTSEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SomfyRTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Somfy RTS cover platform."""
    async_add_entities([SomfyRTSCover(config_entry)])


class SomfyRTSCover(SomfyRTSEntity, CoverEntity, RestoreEntity):
    """A Somfy RTS cover controlled via RF."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_is_closed: bool | None = None
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, entry: SomfyRTSConfigEntry) -> None:
        """Initialize the cover."""
        super().__init__(entry)
        self._attr_unique_id = entry.entry_id

    async def async_added_to_hass(self) -> None:
        """Restore last known cover state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state == STATE_OPEN:
                self._attr_is_closed = False
            elif last_state.state == STATE_CLOSED:
                self._attr_is_closed = True

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_send_command(SomfyRTSButton.UP)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_send_command(SomfyRTSButton.DOWN)
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._async_send_command(SomfyRTSButton.MY)
