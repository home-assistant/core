"""Platform for cover integration."""
from typing import Any

from boschshcpy import SHCSession, SHCShutterControl

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        return round(self._device.level * 100.0)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._device.stop()

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return (
            self._device.operation_state
            == SHCShutterControl.ShutterControlService.State.OPENING
        )

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return (
            self._device.operation_state
            == SHCShutterControl.ShutterControlService.State.CLOSING
        )

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._device.level = 1.0

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._device.level = 0.0

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._device.level = position / 100.0
