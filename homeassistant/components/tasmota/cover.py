"""Support for Tasmota covers."""

from __future__ import annotations

from typing import Any

from hatasmota import const as tasmota_const, shutter as tasmota_shutter
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota cover dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota cover."""
        async_add_entities(
            [TasmotaCover(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(COVER_DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(COVER_DOMAIN),
            async_discover,
        )
    )


class TasmotaCover(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    CoverEntity,
):
    """Representation of a Tasmota cover."""

    _tasmota_entity: tasmota_shutter.TasmotaShutter

    def __init__(self, **kwds: Any) -> None:
        """Initialize the Tasmota cover."""
        self._direction: int | None = None
        self._position: int | None = None
        self._tilt_position: int | None = None

        super().__init__(
            **kwds,
        )

        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        if self._tasmota_entity.supports_tilt:
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.cover_state_updated)
        await super().async_added_to_hass()

    @callback
    def cover_state_updated(self, state: bool, **kwargs: Any) -> None:
        """Handle state updates."""
        self._direction = kwargs["direction"]
        self._position = kwargs["position"]
        self._tilt_position = kwargs["tilt"]
        self.async_write_ha_state()

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._tilt_position

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._direction == tasmota_const.SHUTTER_DIRECTION_UP

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._direction == tasmota_const.SHUTTER_DIRECTION_DOWN

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._position is None:
            return None
        return self._position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._tasmota_entity.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._tasmota_entity.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self._tasmota_entity.set_position(position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._tasmota_entity.stop()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._tasmota_entity.open_tilt()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self._tasmota_entity.close_tilt()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt = kwargs[ATTR_TILT_POSITION]
        await self._tasmota_entity.set_tilt_position(tilt)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._tasmota_entity.stop()
