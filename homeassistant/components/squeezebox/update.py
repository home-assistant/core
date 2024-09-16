"""Platform for update integration for squeezebox."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

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

POLL_AFTER_INSTALL = 120

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
    title: str = SERVER_MODEL + " Plugins"
    installed_version = "current"
    restart_triggered = False

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Support install if we can."""
        return (
            (UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS)
            if self.coordinator.can_server_restart
            else UpdateEntityFeature(0)
        )

    @property
    def release_summary(self) -> None | str:
        """If install is supported give some info."""
        return (
            "Named Plugins will be updated on the next restart. For some installation types, the service will be restarted automatically after the Install button has been selected. Allow enough time for the service to restart. It will become briefly unavailable."
            if self.coordinator.can_server_restart
            else None
        )

    @property
    def in_progress(self) -> bool:
        """Are we restarting."""
        if self.latest_version == self.installed_version and self.restart_triggered:
            _LOGGER.debug("plugin progress reset %s", self.coordinator.lms.name)
            self._cancel_update()
            self.restart_triggered = False
        return self.restart_triggered

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install all plugin updates."""
        _LOGGER.debug(
            "server restart for plugin install on %s", self.coordinator.lms.name
        )
        self.restart_triggered = True
        self.async_write_ha_state()

        result = await self.coordinator.lms.async_query("restartserver")
        _LOGGER.debug("restart server result %s", result)
        if not result:
            self._cancel_update = async_call_later(
                self.hass, POLL_AFTER_INSTALL, self._async_update_catchall
            )
        else:
            self.restart_triggered = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Error trying to update LMS Plugins: Restart failed"
            )

    async def _async_update_catchall(self, now: datetime | None = None) -> None:
        """Request update. clear restart catchall."""
        if self.restart_triggered:
            _LOGGER.debug("server restart catchall for %s", self.coordinator.lms.name)
            self.restart_triggered = False
            self.async_write_ha_state()
            await self.async_update()
