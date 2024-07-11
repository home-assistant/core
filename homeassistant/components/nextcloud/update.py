"""Update data from Nextcoud."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NextcloudConfigEntry
from .entity import NextcloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NextcloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nextcloud update entity."""
    coordinator = entry.runtime_data
    if coordinator.data.get("update_available") is None:
        return
    async_add_entities(
        [
            NextcloudUpdateSensor(
                coordinator, entry, UpdateEntityDescription(key="update")
            )
        ]
    )


class NextcloudUpdateSensor(NextcloudEntity, UpdateEntity):
    """Represents a Nextcloud update entity."""

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self.coordinator.data.get("system_version")

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.coordinator.data.get(
            "update_available_version", self.installed_version
        )

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if self.latest_version:
            ver = "-".join(self.latest_version.split(".")[:3])
            return f"https://nextcloud.com/changelog/#{ver}"
        return None
