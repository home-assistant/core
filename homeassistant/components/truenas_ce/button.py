"""TrueNAS button platform."""

from __future__ import annotations

from logging import getLogger
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .button_types import (  # noqa: F401
    SENSOR_SERVICES,
    SENSOR_TYPES,
    TrueNASButtonEntityDescription,
)
from .const import (
    API_POOL_SCRUB_SCRUB,
    BUTTON_MIGRATION_ROLLBACK,
    BUTTON_STATISTICS_CLEANUP,
    BUTTON_SYSTEM_REFRESH,
    DOMAIN,
    LEGACY_DOMAIN,
    MIGRATION_LEGACY_ENTRY_ID,
    SCRUB_ACTION_START,
)
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import (
    TrueNASEntity,
    async_add_entities,
    format_device_identifier,
    format_unique_id,
)

_LOGGER = getLogger(__name__)

# Updates are centralized in the coordinator; entity actions may run unlimited.
PARALLEL_UPDATES = 0


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TrueNASConfigEntry,
    _async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TrueNAS buttons."""
    dispatcher = {
        "TrueNASButton": TrueNASButton,
        "TrueNASPoolScrubButton": TrueNASPoolScrubButton,
    }
    await async_add_entities(hass, config_entry, dispatcher)

    # The orphaned-statistics cleanup button is a single diagnostic entity per
    # config entry, not tied to a TrueNAS object, so it is added directly.
    coordinator: TrueNASCoordinator | None = get_truenas_coordinator(config_entry)
    if coordinator is None:
        return
    _async_add_entities([TrueNASStatisticsCleanupButton(coordinator)])

    # On-demand data refresh: a diagnostic button that forces an immediate
    # coordinator re-poll (mirrors the system_refresh action). One per entry.
    _async_add_entities([TrueNASRefreshButton(coordinator)])

    # Migration rollback: a safe diagnostic button that only opens the Repairs
    # confirm dialog (it never rolls back directly). Created only after a
    # Community-Edition migration adopted a legacy entry — never on the original
    # "truenas" integration.
    if DOMAIN != LEGACY_DOMAIN and config_entry.data.get(MIGRATION_LEGACY_ENTRY_ID):
        _async_add_entities([TrueNASMigrationRollbackButton(coordinator)])


# ---------------------------
#   TrueNASButton
# ---------------------------
class TrueNASButton(TrueNASEntity, ButtonEntity):
    """Define a TrueNAS run button (one-tap trigger for an on-demand task)."""

    entity_description: TrueNASButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Trigger the configured JSON-RPC method for this object."""
        method = self.entity_description.api_method
        data_path = self.entity_description.data_path
        object_id = self._data.get("id")
        if not method or not data_path or object_id is None:
            _LOGGER.warning(
                "TrueNAS button %s has no api_method or object id; skipping",
                self.entity_id,
            )
            return

        # Trigger the run and show RUNNING immediately (re-synced on next poll).
        await self.coordinator.async_run_task(method, object_id, data_path)


# ---------------------------
#   TrueNASPoolScrubButton
# ---------------------------
class TrueNASPoolScrubButton(TrueNASButton):
    """Scrub button: starts a pool scrub via pool.scrub.scrub."""

    @override
    async def async_press(self) -> None:
        pool_name = self._data.get("pool_name")
        task_id = self._data.get("id")
        if not pool_name or task_id is None:
            _LOGGER.debug(
                "TrueNAS scrub button %s missing pool_name or task id; skipping",
                self.entity_id,
            )
            return
        if not self._data.get("enabled"):
            _LOGGER.debug(
                "TrueNAS scrub button %s: scrub task is disabled; skipping",
                self.entity_id,
            )
            return
        result = await self.coordinator.api.query(
            API_POOL_SCRUB_SCRUB, [pool_name, SCRUB_ACTION_START]
        )
        if result is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="scrub_failed",
                translation_placeholders={
                    "pool": pool_name,
                    "host": self.coordinator.host,
                    "error": str(self.coordinator.api.error or "unknown error"),
                },
            )
        self.coordinator.set_optimistic_running(
            self.entity_description.data_path or "", task_id
        )
        _LOGGER.debug(
            "TrueNAS scrub button %s: started scrub for pool %r",
            self.entity_id,
            pool_name,
        )


# ---------------------------
#   TrueNASStatisticsCleanupButton
# ---------------------------
class TrueNASStatisticsCleanupButton(
    CoordinatorEntity[TrueNASCoordinator], ButtonEntity
):
    """Diagnostic button to delete orphaned recorder statistics.

    Available only while orphans are actually present — independent of whether
    the Repairs issue has been ignored.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = BUTTON_STATISTICS_CLEANUP

    def __init__(self, coordinator: TrueNASCoordinator) -> None:
        """Initialize the cleanup button."""
        super().__init__(coordinator)
        inst = coordinator.config_entry.data[CONF_NAME]
        self._attr_unique_id = format_unique_id(inst, BUTTON_STATISTICS_CLEANUP)
        hostname = coordinator.data.get("system_info", {}).get("hostname", inst)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_device_identifier(inst, hostname))},
        )

    @property
    @override
    def available(self) -> bool:
        """Available only while orphaned statistics exist."""
        return bool(self.coordinator.orphaned_statistics)

    @override
    async def async_press(self) -> None:
        """Clear the orphaned statistics."""
        await self.coordinator.async_clear_orphaned_statistics()


# ---------------------------
#   TrueNASMigrationRollbackButton
# ---------------------------
class TrueNASMigrationRollbackButton(
    CoordinatorEntity[TrueNASCoordinator], ButtonEntity
):
    """Diagnostic button that opens the Community-Edition rollback confirmation.

    It is intentionally non-destructive: pressing it only raises the rollback
    Repairs issue (a confirm dialog), so an accidental press can never tear the
    integration down — the actual rollback happens only after the user confirms
    in Repairs. Available, and the issue re-raisable, only while the disabled
    legacy "truenas" entry still exists.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = BUTTON_MIGRATION_ROLLBACK

    def __init__(self, coordinator: TrueNASCoordinator) -> None:
        """Initialize the rollback button."""
        super().__init__(coordinator)
        inst = coordinator.config_entry.data[CONF_NAME]
        self._attr_unique_id = format_unique_id(inst, BUTTON_MIGRATION_ROLLBACK)
        hostname = coordinator.data.get("system_info", {}).get("hostname", inst)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_device_identifier(inst, hostname))},
        )

    @property
    @override
    def available(self) -> bool:
        """Available only while the legacy entry to roll back to still exists."""
        legacy_id = self.coordinator.config_entry.data.get(MIGRATION_LEGACY_ENTRY_ID)
        return bool(legacy_id and self.hass.config_entries.async_get_entry(legacy_id))

    @override
    async def async_press(self) -> None:
        """Open the rollback confirmation by raising its Repairs issue."""
        self.coordinator.raise_migration_rollback_issue()


# ---------------------------
#   TrueNASRefreshButton
# ---------------------------
class TrueNASRefreshButton(CoordinatorEntity[TrueNASCoordinator], ButtonEntity):
    """Diagnostic button to force an immediate coordinator re-poll of TrueNAS.

    Mirrors the ``system_refresh`` action: it triggers the same update cycle that
    otherwise runs on the poll interval, so the data can be refreshed on demand
    from the UI without waiting for the next poll.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = BUTTON_SYSTEM_REFRESH

    def __init__(self, coordinator: TrueNASCoordinator) -> None:
        """Initialize the refresh button."""
        super().__init__(coordinator)
        inst = coordinator.config_entry.data[CONF_NAME]
        self._attr_unique_id = format_unique_id(inst, BUTTON_SYSTEM_REFRESH)
        hostname = coordinator.data.get("system_info", {}).get("hostname", inst)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_device_identifier(inst, hostname))},
        )

    @override
    async def async_press(self) -> None:
        """Force an immediate coordinator re-poll."""
        await self.coordinator.async_refresh()
