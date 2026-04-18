"""Update platform for Paperless-ngx."""

from __future__ import annotations

from datetime import timedelta

from pypaperless.exceptions import PaperlessConnectionError

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import PaperlessConfigEntry, PaperlessStatusCoordinator
from .entity import PaperlessEntity

PAPERLESS_CHANGELOGS = "https://docs.paperless-ngx.com/changelog/"


PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(hours=24)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx update entities."""

    description = UpdateEntityDescription(
        key="paperless_update",
        translation_key="paperless_update",
        device_class=UpdateDeviceClass.FIRMWARE,
    )

    async_add_entities(
        [
            PaperlessUpdate(
                coordinator=entry.runtime_data.status,
                description=description,
            )
        ],
        update_before_add=True,
    )


class PaperlessUpdate(PaperlessEntity[PaperlessStatusCoordinator], UpdateEntity):
    """Defines a Paperless-ngx update entity."""

    release_url = PAPERLESS_CHANGELOGS

    @property
    def should_poll(self) -> bool:
        """Return True because we need to poll the latest version."""
        return True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self.coordinator.api.host_version

    async def async_update(self) -> None:
        """Update the entity."""
        remote_version = None
        try:
            remote_version = await self.coordinator.api.remote_version()
        except PaperlessConnectionError as err:
            if self._attr_available:
                LOGGER.warning("Could not fetch remote version: %s", err)
                self._attr_available = False
            return

        if remote_version.version is None or remote_version.version == "0.0.0":
            if self._attr_available:
                LOGGER.warning("Remote version is not available or invalid")
                self._attr_available = False
            return

        self._attr_latest_version = remote_version.version.lstrip("v")
        self._attr_available = True
