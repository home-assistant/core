"""Support for covers connected with WMS WebControl pro."""

import logging
from datetime import timedelta
from typing import Any

from wmspro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
    WMS_WebControl_pro_API_actionType,
    WMS_WebControl_pro_API_responseType,
)
from wmspro.destination import Destination

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1

WAREMA_SLAT_CLOSED_ROTATION = 75
WAREMA_SLAT_OPEN_ROTATION = -75
WAREMA_SLAT_ROTATION_RANGE = WAREMA_SLAT_CLOSED_ROTATION - WAREMA_SLAT_OPEN_ROTATION

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based covers from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for dest in hub.dests.values():
        _LOGGER.debug(
            "WMSPRO DEST %s actions: %s",
            dest.name,
            [action.actionDescription.name for action in dest.actions.values()],
        )
        if dest.hasAction(ACTION_DESC.AwningDrive):
            entities.append(WebControlProAwning(config_entry.entry_id, dest))
        if dest.hasAction(ACTION_DESC.ValanceDrive):
            entities.append(WebControlProValance(config_entry.entry_id, dest))
        if dest.hasAction(ACTION_DESC.RollerShutterBlindDrive):
            entities.append(WebControlProRollerShutter(config_entry.entry_id, dest))
        if dest.hasAction(ACTION_DESC.SlatDrive):
            entities.append(WebControlProSlatBlind(config_entry.entry_id, dest))

    async_add_entities(entities)


class WebControlProCover(WebControlProGenericEntity, CoverEntity):
    """Base representation of a WMS based cover."""

    _drive_action_desc: ACTION_DESC
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        action = self._dest.action(self._drive_action_desc)
        if action is None or action["percentage"] is None:
            return None
        return 100 - action["percentage"]

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        action = self._dest.action(self._drive_action_desc)
        await action(percentage=100 - kwargs[ATTR_POSITION])

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self.current_cover_position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        action = self._dest.action(self._drive_action_desc)
        await action(percentage=0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        action = self._dest.action(self._drive_action_desc)
        await action(percentage=100)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        action = self._dest.action(
            ACTION_DESC.ManualCommand,
            WMS_WebControl_pro_API_actionType.Stop,
        )
        await action(responseType=WMS_WebControl_pro_API_responseType.Detailed)


class WebControlProAwning(WebControlProCover):
    """Representation of a WMS based awning."""

    _attr_device_class = CoverDeviceClass.AWNING
    _drive_action_desc = ACTION_DESC.AwningDrive


class WebControlProValance(WebControlProCover):
    """Representation of a WMS based valance."""

    _attr_translation_key = "valance"
    _attr_device_class = CoverDeviceClass.SHADE
    _drive_action_desc = ACTION_DESC.ValanceDrive

    def __init__(self, config_entry_id: str, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        if self._attr_unique_id:
            self._attr_unique_id += "-valance"


class WebControlProRollerShutter(WebControlProCover):
    """Representation of a WMS based roller shutter or blind."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _drive_action_desc = ACTION_DESC.RollerShutterBlindDrive


class WebControlProSlatBlind(WebControlProCover):
    """Representation of a WMS based slat blind."""

    _attr_device_class = CoverDeviceClass.BLIND
    _drive_action_desc = ACTION_DESC.SlatDrive
    _attr_supported_features = (
        WebControlProCover._attr_supported_features
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        if action is None or action["rotation"] is None:
            return None

        rotation = action["rotation"]
        return round(
            (WAREMA_SLAT_CLOSED_ROTATION - rotation)
            / WAREMA_SLAT_ROTATION_RANGE
            * 100
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        tilt_position = kwargs[ATTR_TILT_POSITION]

        rotation = round(
            WAREMA_SLAT_CLOSED_ROTATION
            - (tilt_position / 100 * WAREMA_SLAT_ROTATION_RANGE)
        )

        await action(rotation=rotation)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        await action(rotation=WAREMA_SLAT_OPEN_ROTATION)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        await action(rotation=WAREMA_SLAT_CLOSED_ROTATION)
