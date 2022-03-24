"""Support for Synology DSM update platform."""
from __future__ import annotations

from typing import Any, Final

from synology_dsm.api.core.upgrade import SynoCoreUpgrade

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SynoApi, SynologyDSMBaseEntity
from .const import (
    COORDINATOR_CENTRAL,
    DOMAIN,
    SYNO_API,
    SynologyDSMUpdateEntityEntityDescription,
)

UPDATE_ENTITIES: Final = [
    SynologyDSMUpdateEntityEntityDescription(
        api_key=SynoCoreUpgrade.API_KEY,
        key="update",
        name="DSM Update",
        entity_category=EntityCategory.CONFIG,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up demo update entities."""
    data = hass.data[DOMAIN][entry.unique_id]
    api: SynoApi = data[SYNO_API]
    coordinator = data[COORDINATOR_CENTRAL]

    async_add_entities(
        [
            SynoDSMUpdateEntity(api, coordinator, description)
            for description in UPDATE_ENTITIES
        ]
    )


class SynoDSMUpdateEntity(SynologyDSMBaseEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    entity_description: SynologyDSMUpdateEntityEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMUpdateEntityEntityDescription,
    ) -> None:
        """Initialize the Synology DSM binary_sensor entity."""
        super().__init__(api, coordinator, description)

    @property
    def current_version(self) -> str | None:
        """Version currently in use."""
        return self._api.information.version_string  # type: ignore[no-any-return]

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if not self._api.upgrade.update_available:
            return self.current_version
        return self._api.upgrade.available_version  # type: ignore[no-any-return]

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        base_url = "http://update.synology.com/autoupdate/whatsnew.php?"
        if (details := self._api.upgrade.available_version_details) is not None:
            url = f"{base_url}model={self._api.information.model}&update_version={details['buildnumber']}"
            if details.get("nano") > 0:
                return f"{url}-{details['nano']}"
            return url
        return None
