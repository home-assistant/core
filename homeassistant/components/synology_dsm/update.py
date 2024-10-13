"""Support for Synology DSM update platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from yarl import URL

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SynologyDSMCentralUpdateCoordinator
from .entity import SynologyDSMBaseEntity, SynologyDSMEntityDescription
from .models import SynologyDSMData


@dataclass(frozen=True, kw_only=True)
class SynologyDSMUpdateEntityEntityDescription(
    UpdateEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM update entity."""


UPDATE_ENTITIES: Final = [
    SynologyDSMUpdateEntityEntityDescription(
        api_key=SynoCoreUpgrade.API_KEY,
        key="update",
        translation_key="update",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Synology DSM update entities."""
    data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        SynoDSMUpdateEntity(data.api, data.coordinator_central, description)
        for description in UPDATE_ENTITIES
    )


class SynoDSMUpdateEntity(
    SynologyDSMBaseEntity[SynologyDSMCentralUpdateCoordinator], UpdateEntity
):
    """Mixin for update entity specific attributes."""

    entity_description: SynologyDSMUpdateEntityEntityDescription
    _attr_title = "Synology DSM"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.upgrade) and super().available

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        assert self._api.information is not None
        return self._api.information.version_string

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        assert self._api.upgrade is not None
        if not self._api.upgrade.update_available:
            return self.installed_version
        return self._api.upgrade.available_version

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        assert self._api.information is not None
        assert self._api.upgrade is not None

        if (details := self._api.upgrade.available_version_details) is None:
            return None

        url = URL("http://update.synology.com/autoupdate/whatsnew.php")
        query = {"model": self._api.information.model}
        if details["nano"] > 0:
            query["update_version"] = f"{details['buildnumber']}-{details['nano']}"
        else:
            query["update_version"] = details["buildnumber"]

        return url.update_query(query).human_repr()
