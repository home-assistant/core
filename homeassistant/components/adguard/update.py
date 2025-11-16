"""AdGuard Home Update platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from adguardhome import AdGuardHomeError

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AdGuardConfigEntry, AdGuardData
from .const import DOMAIN
from .entity import AdGuardHomeEntity

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home update entity based on a config entry."""
    data = entry.runtime_data

    if (await data.client.update.update_available()).disabled:
        return

    async_add_entities([AdGuardHomeUpdate(data, entry)], True)


class AdGuardHomeUpdate(AdGuardHomeEntity, UpdateEntity):
    """Defines an AdGuard Home update."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_name = None

    def __init__(
        self,
        data: AdGuardData,
        entry: AdGuardConfigEntry,
    ) -> None:
        """Initialize AdGuard Home update."""
        super().__init__(data, entry)

        self._attr_unique_id = "_".join(
            [DOMAIN, self.adguard.host, str(self.adguard.port), "update"]
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        value = await self.adguard.update.update_available()
        self._attr_installed_version = self.data.version
        self._attr_latest_version = value.new_version
        self._attr_release_summary = value.announcement
        self._attr_release_url = value.announcement_url

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install latest update."""
        try:
            await self.adguard.update.begin_update()
        except AdGuardHomeError as err:
            raise HomeAssistantError(f"Failed to install update: {err}") from err
        self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
