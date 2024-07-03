"""Support for ZHA covers."""

from __future__ import annotations

import functools
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation cover from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.COVER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZhaCover, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZhaCover(ZHAEntity, CoverEntity):
    """Representation of a ZHA cover."""

    def __init__(self, entity_data) -> None:
        """Initialize the ZHA cover."""
        super().__init__(entity_data)

        if self.entity_data.entity.info_object.device_class is not None:
            self._attr_device_class = CoverDeviceClass(
                self.entity_data.entity.info_object.device_class
            )

        self._attr_supported_features: CoverEntityFeature = CoverEntityFeature(
            self.entity_data.entity._attr_supported_features  # noqa: SLF001
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        return {
            "target_lift_position": self.entity_data.entity.state[
                "target_lift_position"
            ],
            "target_tilt_position": self.entity_data.entity.state[
                "target_tilt_position"
            ],
        }

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is closed."""
        return self.entity_data.entity.is_closed

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.entity_data.entity.is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.entity_data.entity.is_closing

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of ZHA cover."""
        return self.entity_data.entity.current_cover_position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        return self.entity_data.entity.current_cover_tilt_position

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.entity_data.entity.async_open_cover()
        await self.async_update_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self.entity_data.entity.async_open_cover_tilt()
        await self.async_update_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.entity_data.entity.async_close_cover()
        await self.async_update_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self.entity_data.entity.async_close_cover_tilt()
        await self.async_update_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.entity_data.entity.async_set_cover_position(
            position=kwargs.get(ATTR_POSITION)
        )
        await self.async_update_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self.entity_data.entity.async_set_cover_tilt_position(
            tilt_position=kwargs.get(ATTR_TILT_POSITION)
        )
        await self.async_update_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.entity_data.entity.async_stop_cover()
        await self.async_update_ha_state()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self.entity_data.entity.async_stop_cover_tilt()
        await self.async_update_ha_state()

    @callback
    def restore_external_state_attributes(self, state: State) -> None:
        """Restore entity state."""
        # Same as `light`, some entity state is not derived from ZCL attributes
        self.entity_data.entity.restore_external_state_attributes(
            state=state.state,
            target_lift_position=state.attributes.get("target_lift_position"),
            target_tilt_position=state.attributes.get("target_tilt_position"),
        )
