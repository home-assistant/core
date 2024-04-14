"""Cover Platform for the Somfy MyLink component."""

import logging
from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_REVERSED_TARGET_IDS,
    DATA_SOMFY_MYLINK,
    DOMAIN,
    MANUFACTURER,
    MYLINK_STATUS,
)

_LOGGER = logging.getLogger(__name__)

MYLINK_COVER_TYPE_TO_DEVICE_CLASS = {
    0: CoverDeviceClass.BLIND,
    1: CoverDeviceClass.SHUTTER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover and configure Somfy covers."""
    reversed_target_ids = config_entry.options.get(CONF_REVERSED_TARGET_IDS, {})

    data = hass.data[DOMAIN][config_entry.entry_id]
    mylink_status = data[MYLINK_STATUS]
    somfy_mylink = data[DATA_SOMFY_MYLINK]
    cover_list = []

    for cover in mylink_status["result"]:
        cover_config = {
            "target_id": cover["targetID"],
            "name": cover["name"],
            "device_class": MYLINK_COVER_TYPE_TO_DEVICE_CLASS.get(
                cover.get("type"), CoverDeviceClass.WINDOW
            ),
            "reverse": reversed_target_ids.get(cover["targetID"], False),
        }

        cover_list.append(SomfyShade(somfy_mylink, **cover_config))

        _LOGGER.info(
            "Adding Somfy Cover: %s with targetID %s",
            cover_config["name"],
            cover_config["target_id"],
        )

    async_add_entities(cover_list)


class SomfyShade(RestoreEntity, CoverEntity):
    """Object for controlling a Somfy cover."""

    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        somfy_mylink,
        target_id,
        name="SomfyShade",
        reverse=False,
        device_class=CoverDeviceClass.WINDOW,
    ):
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = target_id
        self._attr_unique_id = target_id
        self._reverse = reverse
        self._attr_is_closed = None
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._target_id)},
            manufacturer=MANUFACTURER,
            name=name,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._attr_is_closing = True
        self.async_write_ha_state()
        try:
            # Blocks until the close command is sent
            if not self._reverse:
                await self.somfy_mylink.move_down(self._target_id)
            else:
                await self.somfy_mylink.move_up(self._target_id)
            self._attr_is_closed = True
        finally:
            self._attr_is_closing = None
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._attr_is_opening = True
        self.async_write_ha_state()
        try:
            # Blocks until the open command is sent
            if not self._reverse:
                await self.somfy_mylink.move_up(self._target_id)
            else:
                await self.somfy_mylink.move_down(self._target_id)
            self._attr_is_closed = False
        finally:
            self._attr_is_opening = None
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)

    async def async_added_to_hass(self) -> None:
        """Complete the initialization."""
        await super().async_added_to_hass()
        # Restore the last state
        last_state = await self.async_get_last_state()

        if last_state is not None and last_state.state in (
            STATE_OPEN,
            STATE_CLOSED,
        ):
            self._attr_is_closed = last_state.state == STATE_CLOSED
