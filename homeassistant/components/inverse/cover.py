"""Cover support for inverse entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_OPEN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BaseInverseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Cover Inverse config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(registry, config_entry.data[CONF_ENTITY_ID])

    async_add_entities(
        [
            InverseCover(
                hass,
                config_entry.title,
                COVER_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class InverseCover(BaseInverseEntity, CoverEntity):
    """Represents an Inverse Cover."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_title: str,
        domain: str,
        source_entity_id: str,
        unique_id: str,
    ) -> None:
        """Initialize Inverse Cover."""
        super().__init__(hass, config_entry_title, domain, source_entity_id, unique_id)

        # Copy supported features from source entity
        if source_state := hass.states.get(source_entity_id):
            if (
                supported_features := source_state.attributes.get("supported_features")
            ) is not None:
                self._attr_supported_features = CoverEntityFeature(supported_features)
            else:
                self._attr_supported_features = (
                    CoverEntityFeature.OPEN
                    | CoverEntityFeature.CLOSE
                    | CoverEntityFeature.SET_POSITION
                )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (inverted - calls close)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover (inverted - calls open)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position (inverted)."""
        if (position := kwargs.get(ATTR_POSITION)) is not None:
            # Invert position: 0 -> 100, 100 -> 0
            inverted_position = 100 - position
            await self.hass.services.async_call(
                self._source_domain,
                SERVICE_SET_COVER_POSITION,
                {
                    ATTR_ENTITY_ID: self._source_entity_id,
                    ATTR_POSITION: inverted_position,
                },
                blocking=True,
                context=self._context,
            )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover (not inverted)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the cover (not inverted - toggle is toggle)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt (inverted - calls close)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt (inverted - calls open)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position (inverted)."""
        if (tilt_position := kwargs.get(ATTR_TILT_POSITION)) is not None:
            # Invert tilt position: 0 -> 100, 100 -> 0
            inverted_tilt_position = 100 - tilt_position
            await self.hass.services.async_call(
                self._source_domain,
                SERVICE_SET_COVER_TILT_POSITION,
                {
                    ATTR_ENTITY_ID: self._source_entity_id,
                    ATTR_TILT_POSITION: inverted_tilt_position,
                },
                blocking=True,
                context=self._context,
            )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt (not inverted)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the cover tilt (not inverted - toggle is toggle)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TOGGLE_COVER_TILT,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        super().async_state_changed_listener(event)
        if (
            not self.available
            or (state := self.hass.states.get(self._source_entity_id)) is None
        ):
            return

        # Always invert: open becomes closed
        self._attr_is_closed = state.state == STATE_OPEN

        # Invert position: source 0 -> inverse 100, source 100 -> inverse 0
        if (
            current_position := state.attributes.get(ATTR_CURRENT_POSITION)
        ) is not None:
            self._attr_current_cover_position = 100 - current_position

        # Invert tilt position
        if (
            current_tilt := state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        ) is not None:
            self._attr_current_cover_tilt_position = 100 - current_tilt
