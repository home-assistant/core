"""Platform for sensor integration for squeezebox."""

from __future__ import annotations

import logging

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SqueezeboxConfigEntry
from .const import SERVER_MODEL, STATUS_QUERY_VERSION, STATUS_SENSOR_NEWVERSION
from .entity import LMSStatusEntity

SENSORS: tuple[UpdateEntityDescription, ...] = (
    UpdateEntityDescription(
        key=STATUS_SENSOR_NEWVERSION,
        entity_registry_visible_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    async_add_entities(
        ServerStatusUpdate(entry.runtime_data.coordinator, description)
        for description in SENSORS
    )


class ServerStatusUpdate(LMSStatusEntity, UpdateEntity):
    """LMS Status update sensor from LMS via cooridnatior."""

    title: str = SERVER_MODEL

    @property
    def installed_version(self) -> str:
        """LMS Status directly from coordinator data."""
        return str(self.coordinator.data[STATUS_QUERY_VERSION])

    @property
    def latest_version(self) -> StateType:
        """LMS Status directly from coordinator data."""
        return str(self.coordinator.data[self.entity_description.key] or self.coordinator.data[STATUS_QUERY_VERSION])
