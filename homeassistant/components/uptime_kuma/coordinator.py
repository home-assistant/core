"""Coordinator for the Uptime Kuma integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pythonkuma import (
    UpdateException,
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
    UptimeKumaMonitor,
    UptimeKumaVersion,
)
from pythonkuma.update import LatestRelease, UpdateChecker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
SCAN_INTERVAL_UPDATES = timedelta(hours=3)

type UptimeKumaConfigEntry = ConfigEntry[UptimeKumaDataUpdateCoordinator]


class UptimeKumaDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str | int, UptimeKumaMonitor]]
):
    """Update coordinator for Uptime Kuma."""

    config_entry: UptimeKumaConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: UptimeKumaConfigEntry
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        session = async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL])
        self.api = UptimeKuma(
            session, config_entry.data[CONF_URL], config_entry.data[CONF_API_KEY]
        )
        self.version: UptimeKumaVersion | None = None

    async def _async_update_data(self) -> dict[str | int, UptimeKumaMonitor]:
        """Fetch the latest data from Uptime Kuma."""

        try:
            metrics = await self.api.metrics()
        except UptimeKumaAuthenticationException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed_exception",
            ) from e
        except UptimeKumaException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_failed_exception",
            ) from e
        else:
            async_migrate_entities_unique_ids(self.hass, self, metrics)
            self.version = self.api.version

            return metrics


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant,
    coordinator: UptimeKumaDataUpdateCoordinator,
    metrics: dict[str | int, UptimeKumaMonitor],
) -> None:
    """Migrate unique_ids in the entity registry after updating Uptime Kuma."""

    if (
        coordinator.version is coordinator.api.version
        or int(coordinator.api.version.major) < 2
    ):
        return

    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, coordinator.config_entry.entry_id
    )

    for registry_entry in registry_entries:
        name = registry_entry.unique_id.removeprefix(
            f"{registry_entry.config_entry_id}_"
        ).removesuffix(f"_{registry_entry.translation_key}")
        if monitor := next(
            (
                m
                for m in metrics.values()
                if m.monitor_name == name and m.monitor_id is not None
            ),
            None,
        ):
            entity_registry.async_update_entity(
                registry_entry.entity_id,
                new_unique_id=f"{registry_entry.config_entry_id}_{monitor.monitor_id!s}_{registry_entry.translation_key}",
            )


class UptimeKumaSoftwareUpdateCoordinator(DataUpdateCoordinator[LatestRelease]):
    """Uptime Kuma coordinator for retrieving update information."""

    def __init__(self, hass: HomeAssistant, update_checker: UpdateChecker) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_UPDATES,
        )
        self.update_checker = update_checker

    async def _async_update_data(self) -> LatestRelease:
        """Fetch data."""
        try:
            return await self.update_checker.latest_release()
        except UpdateException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_check_failed",
            ) from e
