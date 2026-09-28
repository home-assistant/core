"""Platform for cover integration."""

from typing import TYPE_CHECKING, Any, override

from boschshcpy import SHCMicromoduleBlinds, SHCShutterControl, ShutterControlService

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC cover platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        ShutterControlCover(
            hass=hass,
            device=cover,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for cover in (
            *session.device_helper.shutter_controls,
            *session.device_helper.micromodule_shutter_controls,
        )
    )
    async_add_entities(
        BlindsControlCover(
            hass=hass,
            device=blind,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for blind in session.device_helper.micromodule_blinds
    )


class ShutterControlCover(SHCEntity, CoverEntity):
    """Representation of a SHC shutter control device."""

    _attr_name = None
    _device: SHCShutterControl
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    @override
    def device_class(self) -> CoverDeviceClass:
        """Return the device class."""
        if self._device.device_model == "MICROMODULE_AWNING":
            return CoverDeviceClass.AWNING
        return CoverDeviceClass.SHUTTER

    @property
    @override
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        return round(self._device.level * 100.0)

    @override
    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._device.stop()

    @property
    @override
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    @property
    @override
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._device.operation_state is ShutterControlService.State.OPENING

    @property
    @override
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._device.operation_state is ShutterControlService.State.CLOSING

    @override
    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._device.level = 1.0

    @override
    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._device.level = 0.0

    @override
    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._device.level = position / 100.0


class BlindsControlCover(ShutterControlCover):
    """Representation of a SHC micromodule blinds cover device."""

    _device: SHCMicromoduleBlinds
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    @property
    @override
    def device_class(self) -> CoverDeviceClass:
        """Return the device class."""
        return CoverDeviceClass.BLIND

    @override
    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._device.stop_blinds()

    @property
    @override
    def current_cover_tilt_position(self) -> int:
        """Return the current cover tilt position."""
        return round((1.0 - self._device.current_angle) * 100.0)

    @override
    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        self._device.target_angle = 0.0

    @override
    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        self._device.target_angle = 1.0

    @override
    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        self._device.target_angle = 1.0 - (tilt_position / 100.0)
