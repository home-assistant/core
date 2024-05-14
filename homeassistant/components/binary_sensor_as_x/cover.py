"""Cover support for binary_sensor entities."""

from __future__ import annotations

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BaseDeviceClassEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Cover Binary sensor config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            CoverBinarySensor(
                hass,
                config_entry.title,
                COVER_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class CoverBinarySensor(BaseDeviceClassEntity, CoverEntity):
    """Represents a Binary sensor as a Cover."""

    _attr_supported_features = CoverEntityFeature(0)
    _accepted_device_classes = CoverDeviceClass

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        super().async_state_changed_listener(event)
        if (
            not self.available
            or (state := self.hass.states.get(self._binary_sensor_entity_id)) is None
        ):
            return

        self._attr_is_closed = state.state != STATE_ON
