"""Data coordinator for the Beatbot integration."""

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotClient,
    BeatbotConnectionError,
    BeatbotDeviceData,
    BeatbotEvent,
    ProductCategory,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    NETWORK_REFRESH_INTERVAL,
    POST_CONTROL_REFRESH_DELAY,
    SUPPORTED_PRODUCT_IDS,
)

if TYPE_CHECKING:
    from . import BeatbotConfigEntry

_LOGGER = logging.getLogger(__name__)
_MISSING_DEVICE_CONFIRMATIONS = 3


class BeatbotCoordinator(DataUpdateCoordinator[dict[str, BeatbotDeviceData]]):
    """Coordinate Beatbot cloud data and device reconciliation."""

    config_entry: BeatbotConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: BeatbotClient,
        config_entry: BeatbotConfigEntry,
    ) -> None:
        """Initialize the Beatbot coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=NETWORK_REFRESH_INTERVAL),
            config_entry=config_entry,
        )
        self.api = api
        self._missing_device_counts: dict[str, int] = {}
        self._reload_scheduled = False
        # One delayed post-control reconciliation task per device. A later
        # command replaces the pending task for that device (debounce), while
        # commands for different devices remain independent.
        self._refresh_tasks: dict[str, asyncio.Task[None]] = {}

    @override
    async def _async_update_data(self) -> dict[str, BeatbotDeviceData]:
        try:
            devices = await self.api.get_devices()
        except BeatbotAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except BeatbotConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # Gate first by supported product line, then by verified model.
        result: dict[str, BeatbotDeviceData] = {}
        for d in devices:
            if d.product_category != ProductCategory.POOL_CLEAN_BOT:
                _LOGGER.debug(
                    "Skipping device %s (productId=%s): product category %r is "
                    "not supported by this integration",
                    d.device_id,
                    d.product_id,
                    d.product_category,
                )
                continue
            if d.product_id not in SUPPORTED_PRODUCT_IDS:
                _LOGGER.debug(
                    "Skipping device %s: productId %r is not on the verified "
                    "allow-list (add it to SUPPORTED_PRODUCT_IDS to enable)",
                    d.device_id,
                    d.product_id,
                )
                continue
            result[d.device_id] = d

        # Runtime state is best-effort: a connection failure must not wipe the
        # entities — keep discovery identity data and last-known values. An auth
        # failure still escalates to reauth, since the token is invalid for both
        # endpoints.
        try:
            states = await self.api.get_device_states()
        except BeatbotAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except BeatbotConnectionError as err:
            _LOGGER.warning(
                "Device state fetch failed, using discovery-only data: %s", err
            )
            states = {}
        else:
            _LOGGER.debug(
                "Beatbot state pull completed (source=batch, deviceCount=%s)",
                len(states),
            )

        previous_data = self.data if isinstance(self.data, dict) else {}
        for device_id, device in result.items():
            if (state := states.get(device_id)) is not None:
                self._apply_state_with_logging(
                    device_id,
                    device,
                    state.get("states"),
                    state.get("is_online"),
                    source="batch",
                )
            elif (previous_device := previous_data.get(device_id)) is not None:
                # Discovery and runtime state are separate endpoints. Preserve
                # the last-known state when the batch response is partial or
                # unavailable, while retaining fresh discovery metadata.
                device.copy_runtime_state_from(previous_device)
        self._reconcile_device_set(result)
        return result

    @callback
    def _reconcile_device_set(self, result: dict[str, BeatbotDeviceData]) -> None:
        """Reconcile successful discovery results with the active device set."""
        initial_refresh = not isinstance(self.data, dict)
        previous_data = self.data if isinstance(self.data, dict) else {}
        previous_ids = set(previous_data) | self._registered_device_ids()
        current_ids = set(result)
        added_ids = set() if initial_refresh else current_ids - previous_ids
        missing_ids = previous_ids - current_ids

        for device_id in current_ids:
            self._missing_device_counts.pop(device_id, None)

        confirmed_removed: set[str] = set()
        for device_id in missing_ids:
            count = self._missing_device_counts.get(device_id, 0) + 1
            self._missing_device_counts[device_id] = count
            if count >= _MISSING_DEVICE_CONFIRMATIONS:
                confirmed_removed.add(device_id)
            elif device_id in previous_data:
                # Keep the last-known device until absence is confirmed. This
                # prevents entity callbacks from reading a missing data key.
                result[device_id] = previous_data[device_id]

        for device_id in confirmed_removed:
            # Keep it alive until reload unloads the existing platform entities.
            if device_id in previous_data:
                result[device_id] = previous_data[device_id]
            self._remove_device_from_registries(device_id)
            self._missing_device_counts.pop(device_id, None)

        if added_ids or confirmed_removed:
            _LOGGER.debug(
                "Device discovery changed; added=%s removed=%s",
                sorted(added_ids),
                sorted(confirmed_removed),
            )
            self._schedule_entry_reload()

    @callback
    def _registered_device_ids(self) -> set[str]:
        """Return Beatbot device IDs still associated with this config entry."""
        registry = dr.async_get(self.hass)
        device_ids: set[str] = set()
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            for domain, identifier in device.identifiers:
                if domain == DOMAIN:
                    device_ids.add(identifier)
        return device_ids

    @callback
    def _remove_device_from_registries(self, device_id: str) -> None:
        """Remove one confirmed-absent device and all of its entities."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
        if device is None:
            return
        entity_registry = er.async_get(self.hass)
        for entity in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            if entity.config_entry_id == self.config_entry.entry_id:
                entity_registry.async_remove(entity.entity_id)
        device_registry.async_update_device(
            device.id, remove_config_entry_id=self.config_entry.entry_id
        )

    @callback
    def _schedule_entry_reload(self) -> None:
        """Reload platforms once after a confirmed topology change."""
        if self._reload_scheduled:
            return
        entry_id = self.config_entry.entry_id
        self._reload_scheduled = True

        async def _reload() -> None:
            try:
                await self.hass.config_entries.async_reload(entry_id)
            finally:
                self._reload_scheduled = False

        self.hass.async_create_task(_reload(), f"beatbot_reconcile_{entry_id}")

    async def async_refresh_device_state(self, device_id: str) -> None:
        """Fetch state for one device and push it to entities immediately.

        Used after a control command (start/pause/return/work_mode) to confirm
        the new state quickly and cheaply: a single `GET /devices/{id}/state`
        instead of re-running the full discovery + batch-state refresh. The
        regular reconciliation poll still runs as normal for everything else.

        Waits `POST_CONTROL_REFRESH_DELAY` before fetching: the device does
        not report the new state the instant the action is issued, so reading
        immediately can return the previous value.

        Best-effort like the batch path: a connection failure is logged and
        skipped (last-known values stay), while an auth failure escalates to
        reauth since the token is invalid.
        """
        await asyncio.sleep(POST_CONTROL_REFRESH_DELAY)
        try:
            state = await self.api.get_device_state(device_id)
        except BeatbotAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except BeatbotConnectionError as err:
            _LOGGER.warning(
                "Single-device state fetch failed for %s: %s", device_id, err
            )
            return

        device = self.data.get(device_id)
        if device is None:
            return
        state_values = state.get("states")
        is_online = state.get("is_online")
        _LOGGER.debug(
            "Beatbot state pull completed "
            "(source=post_control, deviceId=%s, states=%r, online=%s)",
            device_id,
            state_values,
            is_online,
        )
        self._apply_state_with_logging(
            device_id,
            device,
            state_values,
            is_online,
            source="post_control",
        )
        # Push the in-place update to listeners and reset the poll timer so
        # we don't double-fetch right after this manual update.
        self.async_set_updated_data(self.data)

    @callback
    def async_apply_device_event(
        self,
        event: BeatbotEvent,
    ) -> None:
        """Overlay a pushed state delta without changing the poll cadence."""
        device = self.data.get(event.device_id)
        if device is None:
            _LOGGER.debug("Ignoring event for undiscovered device %s", event.device_id)
            return
        if not event.apply_to(device):
            return
        _LOGGER.debug(
            "Applied Beatbot state event (deviceId=%s, type=%s)",
            event.device_id,
            event.event_type,
        )
        # DataUpdateCoordinator.async_set_updated_data resets the next poll
        # deadline. Notify listeners directly so steady event traffic cannot
        # postpone the source-of-truth reconciliation poll indefinitely.
        self.last_update_success = True
        self.async_update_listeners()

    @staticmethod
    def _apply_state_with_logging(
        device_id: str,
        device: BeatbotDeviceData,
        states: dict[str, Any] | None,
        is_online: bool | None,
        *,
        source: str,
    ) -> None:
        """Apply state and log useful field-level changes without credentials."""
        _LOGGER.debug(
            "Applying Beatbot state update (source=%s, deviceId=%s)",
            source,
            device_id,
        )
        device.apply_state(states, is_online)

    @callback
    def async_schedule_device_state_refresh(self, device_id: str) -> None:
        """Schedule a delayed single-device state refresh without blocking.

        WebSocket events remain the primary real-time update path. This
        delayed GET is a reconciliation fallback for dropped or delayed push
        events. Repeated commands for one device are debounced so only the
        latest scheduled GET runs.
        """
        previous = self._refresh_tasks.get(device_id)
        if previous is not None:
            previous.cancel()

        async def _refresh() -> None:
            try:
                await self.async_refresh_device_state(device_id)
            except ConfigEntryAuthFailed:
                _LOGGER.warning(
                    "Post-control refresh authorization failed for %s; "
                    "starting reauthentication",
                    device_id,
                )
                self.config_entry.async_start_reauth(self.hass)
            finally:
                current = asyncio.current_task()
                if self._refresh_tasks.get(device_id) is current:
                    self._refresh_tasks.pop(device_id, None)

        self._refresh_tasks[device_id] = self.hass.async_create_task(
            _refresh(), f"beatbot_post_control_refresh_{device_id}"
        )

    @callback
    def async_cancel_pending_refreshes(self) -> None:
        """Cancel any in-flight post-control refresh tasks.

        Call from async_unload_entry so a refresh sleeping inside its
        POST_CONTROL_REFRESH_DELAY window is cancelled rather than left to
        run against a coordinator/api/session that is being torn down.
        """
        for task in self._refresh_tasks.values():
            task.cancel()
        self._refresh_tasks.clear()
