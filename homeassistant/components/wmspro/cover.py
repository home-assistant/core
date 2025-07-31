"""Support for covers connected with WMS WebControl pro."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from wmspro.const import (
    WMS_WebControl_pro_API_actionDescription,
    WMS_WebControl_pro_API_actionType,
    WMS_WebControl_pro_API_responseType,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1
SLAT_ROTATION_MIN = -45
SLAT_ROTATION_MAX = 90


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based covers from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for dest in hub.dests.values():
        if dest.hasAction(WMS_WebControl_pro_API_actionDescription.AwningDrive):
            entities.append(WebControlProAwning(config_entry.entry_id, dest))
        elif dest.hasAction(
            WMS_WebControl_pro_API_actionDescription.RollerShutterBlindDrive
        ):
            entities.append(WebControlProRollerShutter(config_entry.entry_id, dest))
        elif dest.action(
            WMS_WebControl_pro_API_actionDescription.SlatDrive
        ) and dest.action(WMS_WebControl_pro_API_actionDescription.SlatRotate):
            entities.append(WebControlProSlatRotate(config_entry.entry_id, dest))
        elif dest.action(WMS_WebControl_pro_API_actionDescription.SlatDrive):
            entities.append(WebControlProSlat(config_entry.entry_id, dest))

    async_add_entities(entities)


class WebControlProCover(WebControlProGenericEntity, CoverEntity):
    """Base representation of a WMS based cover."""

    _drive_action_desc: WMS_WebControl_pro_API_actionDescription
    _attr_name = None

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
            WMS_WebControl_pro_API_actionDescription.ManualCommand,
            WMS_WebControl_pro_API_actionType.Stop,
        )
        await action(responseType=WMS_WebControl_pro_API_responseType.Detailed)


class WebControlProAwning(WebControlProCover):
    """Representation of a WMS based awning."""

    _attr_device_class = CoverDeviceClass.AWNING
    _drive_action_desc = WMS_WebControl_pro_API_actionDescription.AwningDrive


class WebControlProRollerShutter(WebControlProCover):
    """Representation of a WMS based roller shutter or blind."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _drive_action_desc = (
        WMS_WebControl_pro_API_actionDescription.RollerShutterBlindDrive
    )


class WebControlProSlat(WebControlProCover):
    """Representation of a WMS based blind using a slat drive."""

    _attr_device_class = CoverDeviceClass.BLIND
    _drive_action_desc = WMS_WebControl_pro_API_actionDescription.SlatDrive


class WebControlProSlatRotate(WebControlProSlat):
    """Representation of a WMS based blind which supports tilting."""

    _tilt_action_desc = WMS_WebControl_pro_API_actionDescription.SlatRotate

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover and tilt like the hub."""
        await super().async_open_cover(**kwargs)
        await self.async_open_cover_tilt(**kwargs)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover and tilt like the hub."""
        await super().async_close_cover(**kwargs)
        await self.async_close_cover_tilt(**kwargs)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        action = self._dest.action(self._tilt_action_desc)
        return ranged_value_to_percentage(
            (
                max(action.minValue, SLAT_ROTATION_MIN),
                min(action.maxValue, SLAT_ROTATION_MAX),
            ),
            action["rotation"],
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position."""
        action = self._dest.action(self._tilt_action_desc)
        rotation = percentage_to_ranged_value(
            (
                max(action.minValue, SLAT_ROTATION_MIN),
                min(action.maxValue, SLAT_ROTATION_MAX),
            ),
            kwargs[ATTR_TILT_POSITION],
        )
        await action(rotation=rotation)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        action = self._dest.action(self._tilt_action_desc)
        await action(rotation=min(action.maxValue, SLAT_ROTATION_MAX))

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        action = self._dest.action(self._tilt_action_desc)
        await action(rotation=max(action.minValue, SLAT_ROTATION_MIN))
