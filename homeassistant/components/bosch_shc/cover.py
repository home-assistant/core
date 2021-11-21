"""Platform for cover integration."""
from boschshcpy import SHCSession, SHCShutterControl

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHUTTER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC cover platform."""

    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for cover in session.device_helper.shutter_controls:
        entities.append(
            ShutterControlCover(
                device=cover,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class ShutterControlCover(SHCEntity, CoverEntity):
    """Representation of a SHC shutter control device."""

    _attr_device_class = DEVICE_CLASS_SHUTTER
    _attr_supported_features = (
        SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
    )

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        return round(self._device.level * 100.0)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._device.stop()

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return (
            self._device.operation_state
            == SHCShutterControl.ShutterControlService.State.OPENING
        )

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return (
            self._device.operation_state
            == SHCShutterControl.ShutterControlService.State.CLOSING
        )

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._device.level = 1.0

    def close_cover(self, **kwargs):
        """Close cover."""
        self._device.level = 0.0

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._device.level = position / 100.0
