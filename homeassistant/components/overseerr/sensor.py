"""Implementation of the Radarr sensor."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from overseerr import exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import OverseerrRequestUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    overseer_coordinator: OverseerrRequestUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    sensors = []

    for sensor_label, sensor_data in SENSOR_TYPES.items():
        sensor_type = sensor_data["type"]
        sensor_icon = sensor_data["icon"]
        sensors.append(
            OverseerrSensor(
                sensor_label, sensor_type, overseer_coordinator, sensor_icon
            )
        )

    async_add_entities(sensors)


class OverseerrSensor(Entity):
    """Representation of an Overseerr sensor."""

    def __init__(
        self,
        label,
        sensor_type,
        overseer_coordinator: OverseerrRequestUpdateCoordinator,
        icon,
    ) -> None:
        """Initialize the sensor."""
        self._state: float | str | None = None
        self._label = label
        self._type = sensor_type
        self._overseer_coordinator: OverseerrRequestUpdateCoordinator = (
            overseer_coordinator
        )
        self._icon = icon
        self._last_request = None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return f"Overseerr {self._type}"

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self) -> float | str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Attributes."""
        # Ensure a dictionary is always returned
        return self._last_request if self._last_request is not None else {}

    def update(self) -> None:
        """Update the sensor."""
        _LOGGER.debug("Update Overseerr sensor: %s", self.name)
        try:
            request_count = self._overseer_coordinator.data.request_count

            if request_count is not None:
                if self._label == "movies" and request_count.movie is not None:
                    self._state = request_count.movie
                elif self._label == "total" and request_count.total is not None:
                    self._state = request_count.total
                elif self._label == "tv" and request_count.tv is not None:
                    self._state = request_count.tv
                elif self._label == "pending" and request_count.pending is not None:
                    self._state = request_count.pending
                elif self._label == "approved" and request_count.approved is not None:
                    self._state = request_count.approved
                elif self._label == "available" and request_count.available is not None:
                    self._state = request_count.available
            else:
                _LOGGER.warning("Request count data is None")
        except exceptions.OpenApiException as err:
            _LOGGER.warning("Unable to update Overseerr sensor: %s", err)
            self._state = None
