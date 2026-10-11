"""Data coordinator for the Beatbot integration."""

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NETWORK_REFRESH_INTERVAL

if TYPE_CHECKING:
    from . import BeatbotConfigEntry

_LOGGER = logging.getLogger(__name__)


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
        self._pending_events: list[BeatbotEvent] | None = None
        self.api = api
        self._reload_scheduled = False

    @override
    async def _async_update_data(self) -> dict[str, BeatbotDeviceData]:
        self._pending_events = []
        try:
            result = await self._async_fetch_data()
            # Preserve pushes received while the REST snapshot was being fetched.
            for event in self._pending_events:
                if (device := result.get(event.device_id)) is not None:
                    event.apply_to(device)
            return result
        finally:
            self._pending_events = None

    async def _async_fetch_data(self) -> dict[str, BeatbotDeviceData]:
        """Fetch discovery and runtime state from the cloud."""
        try:
            devices = await self.api.get_devices()
        except BeatbotAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except BeatbotConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # The Core integration exposes only pool cleaners in its initial platform.
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
            result[d.device_id] = d

        try:
            states = await self.api.get_device_states()
        except BeatbotAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except BeatbotConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
        _LOGGER.debug(
            "Beatbot state pull completed (source=batch, deviceCount=%s)",
            len(states),
        )

        for device_id, device in result.items():
            if (state := states.get(device_id)) is not None:
                self._apply_state_with_logging(
                    device_id,
                    device,
                    state.get("states"),
                    state.get("is_online"),
                    source="batch",
                )
            else:
                device.is_online = False
        self._reconcile_device_set(result)
        return result

    @callback
    def _reconcile_device_set(self, result: dict[str, BeatbotDeviceData]) -> None:
        """Reconcile successful discovery results with the active device set."""
        initial_refresh = not isinstance(self.data, dict)
        previous_data = self.data if isinstance(self.data, dict) else {}
        previous_ids = set(previous_data)
        current_ids = set(result)
        added_ids = set() if initial_refresh else current_ids - previous_ids

        for device_id in previous_ids - current_ids:
            # Retained so the registry entries survive until a later PR adds
            # removal, but neither discovery nor the batch state confirmed it,
            # so its cached state is not online.
            retained = previous_data[device_id]
            retained.is_online = False
            result[device_id] = retained

        if added_ids:
            _LOGGER.debug("Device discovery changed; added=%s", sorted(added_ids))
            self._schedule_entry_reload()

    @callback
    def _schedule_entry_reload(self) -> None:
        """Reload platforms once when new devices are discovered."""
        if self._reload_scheduled:
            return
        entry_id = self.config_entry.entry_id
        self._reload_scheduled = True
        self.hass.config_entries.async_schedule_reload(entry_id)

    @callback
    def async_apply_device_event(
        self,
        event: BeatbotEvent,
    ) -> None:
        """Overlay a pushed state delta without changing the poll cadence."""
        if self._pending_events is not None:
            self._pending_events.append(event)
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
