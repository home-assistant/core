"""Support for Curve sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_SEGMENTS, CONF_SOURCE
from .helpers import interpolate_curve, parse_segments
from .models import CurveSegment

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .types import CurveConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CurveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Curve sensor from config entry."""
    name: str = config_entry.options[CONF_NAME]
    source_entity: str | None = config_entry.options.get(CONF_SOURCE)
    segments_data: list[dict[str, Any]] = config_entry.options[CONF_SEGMENTS]
    segments = parse_segments(segments_data)
    curve_sensor = CurveSensor(
        name=name,
        source_entity=source_entity,
        segments=segments,
        unique_id=config_entry.entry_id,
    )

    async_add_entities([curve_sensor])


class CurveSensor(SensorEntity):
    """Representation of a Curve sensor."""

    _attr_should_poll = False
    _attr_icon = "mdi:chart-bell-curve"

    def __init__(
        self,
        *,
        name: str,
        source_entity: str | None,
        segments: list[CurveSegment],
        unique_id: str,
    ) -> None:
        """Initialize the Curve sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._source_entity = source_entity
        self._segments = segments
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Handle getting added to Home Assistant."""
        await super().async_added_to_hass()

        if self._source_entity:
            # Subscribe to state changes of the source entity, if any
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._source_entity,
                    self._handle_state_change,
                )
            )

            if (state := self.hass.states.get(self._source_entity)) is not None:
                self._process_state(state.state)
                self.async_write_ha_state()
        else:  # No source entity - sensor is available but has no value
            self._attr_available = True

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Handle state changes of the source entity."""
        new_state = event.data["new_state"]

        if new_state is None:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._process_state(new_state.state)
        self.async_write_ha_state()

    @property
    def segments(self) -> list[CurveSegment]:
        """Return the curve segments for template use."""
        return self._segments

    def _process_state(self, state: str) -> None:
        """Process the state value and apply curve transformation."""
        # (STATE_UNAVAILABLE, STATE_UNKNOWN) will fail the cast and return None.
        try:
            x_value = float(state)
            y_value = interpolate_curve(x_value, self._segments)
        except (ValueError, TypeError):
            y_value = None
        self._attr_native_value = y_value
        self._attr_available = y_value is not None
