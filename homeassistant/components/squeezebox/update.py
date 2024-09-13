"""Platform for update integration for squeezebox."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SqueezeboxConfigEntry
from .const import (
    SERVER_MODEL,
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_NEWPLUGINS,
    STATUS_SENSOR_NEWVERSION,
)
from .entity import LMSStatusEntity

newserver = UpdateEntityDescription(
    key=STATUS_SENSOR_NEWVERSION,
)

newplugins = UpdateEntityDescription(
    key=STATUS_SENSOR_NEWPLUGINS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    async_add_entities(
        [
            ServerStatusUpdateLMS(entry.runtime_data.coordinator, newserver),
            ServerStatusUpdatePlugins(entry.runtime_data.coordinator, newplugins),
        ]
    )


class ServerStatusUpdate(LMSStatusEntity, UpdateEntity):
    """LMS Status update sensors via cooridnatior."""

    @property
    def latest_version(self) -> str:
        """LMS Status directly from coordinator data."""
        return str(self.coordinator.data[self.entity_description.key])


class ServerStatusUpdateLMS(ServerStatusUpdate):
    """LMS Status update sensor from LMS via cooridnatior."""

    title: str = SERVER_MODEL

    @property
    def installed_version(self) -> str:
        """LMS Status directly from coordinator data."""
        return str(self.coordinator.data[STATUS_QUERY_VERSION])


class ServerStatusUpdatePlugins(ServerStatusUpdate):
    """LMS Plugings update sensor from LMS via cooridnatior."""

    auto_update = True
    supported_features = UpdateEntityFeature.INSTALL
    release_summary = "Named Plugins will be updated on the next restart. For some installation types, the service will be restarted automatically after the Install button has been selected. Allow enough time for the service to restart. It will become briefly unavailable."
    title: str = SERVER_MODEL + " Plugins"
    installed_version = "current"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install all plugin updates."""
        _LOGGER.debug("server restart for plugin install")
        await self.coordinator.lms.async_query("restartserver")
