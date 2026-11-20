"""Cover Platform for the Somfy MyLink component."""

import logging
from typing import Any, override

from pysomfymylink import Shade, SomfyMyLink

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import SomfyMyLinkConfigEntry
from .const import CONF_REVERSED_TARGET_IDS, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

MYLINK_COVER_TYPE_TO_DEVICE_CLASS: dict[int | None, CoverDeviceClass] = {
    0: CoverDeviceClass.BLIND,
    1: CoverDeviceClass.SHUTTER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SomfyMyLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover and configure Somfy covers."""
    reversed_target_ids: dict[str, bool] = config_entry.options.get(
        CONF_REVERSED_TARGET_IDS, {}
    )

    somfy_mylink = config_entry.runtime_data.somfy_mylink
    cover_list = []

    for shade in config_entry.runtime_data.shades:
        cover_list.append(
            SomfyShade(
                somfy_mylink,
                shade,
                reverse=reversed_target_ids.get(shade.target_id, False),
            )
        )

        _LOGGER.debug(
            "Adding Somfy Cover: %s with targetID %s",
            shade.name,
            shade.target_id,
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
        somfy_mylink: SomfyMyLink,
        shade: Shade,
        *,
        reverse: bool = False,
    ) -> None:
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = shade.target_id
        self._attr_unique_id = shade.target_id
        self._reverse = reverse
        self._attr_is_closed = None
        self._attr_device_class = MYLINK_COVER_TYPE_TO_DEVICE_CLASS.get(
            shade.cover_type, CoverDeviceClass.WINDOW
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._target_id)},
            manufacturer=MANUFACTURER,
            name=shade.name,
        )

    @override
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

    @override
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

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)

    @override
    async def async_added_to_hass(self) -> None:
        """Complete the initialization."""
        await super().async_added_to_hass()
        # Restore the last state
        last_state = await self.async_get_last_state()

        if last_state is not None and last_state.state in (
            CoverState.OPEN,
            CoverState.CLOSED,
        ):
            self._attr_is_closed = last_state.state == CoverState.CLOSED
