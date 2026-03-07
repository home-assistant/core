"""DataUpdateCoordinator for the PAJ GPS integration.

Responsibilities:
- Own the single PajGpsApi instance for the lifetime of a config entry.
- Drive two update tiers at different frequencies:
    Tier 1 — device list       every DEVICES_INTERVAL seconds
    Tier 2 — positions every POSITIONS_INTERVAL seconds
- Push CoordinatorData snapshots to entities as soon as each response arrives.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging
import time

import aiohttp
from pajgps_api import PajGpsApi
from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.pajgps_api_error import (
    AuthenticationError,
    PajGpsApiError,
    TokenRefreshError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICES_INTERVAL, DOMAIN, POSITIONS_INTERVAL
from .device_queue import DeviceRequestQueue

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CoordinatorData — immutable snapshot of all PAJ GPS data
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CoordinatorData:
    """Typed, copy-on-write snapshot of all PAJ GPS data.

    Always replace via dataclasses.replace() — never mutate in place.
    """

    # All devices in the account (includes alarm enabled/disabled flags)
    devices: list[Device] = dataclasses.field(default_factory=list)

    # device_id → last TrackPoint
    positions: dict[int, TrackPoint] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# PajGpsCoordinator — main coordinator
# ---------------------------------------------------------------------------


class PajGpsCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator for the PAJ GPS integration.

    Drives two update tiers at different rates and pushes partial data
    snapshots to entities as soon as each response arrives.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict,
        config_entry: ConfigEntry | None = None,
        websession: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the coordinator from config-entry data."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POSITIONS_INTERVAL),
            config_entry=config_entry,
        )

        self.api = PajGpsApi(
            email=entry_data["email"],
            password=entry_data["password"],
            websession=websession,
        )
        self._entry_data = entry_data
        self._queue = DeviceRequestQueue()
        self._owns_websession = websession is None

        # Tier timestamps — initialized to 0 so every tier fires on first call
        self._last_devices_fetch: float = 0.0
        self._last_positions_fetch: float = 0.0

        # Flag to distinguish first call from subsequent ones
        self._initial_refresh_done: bool = False

        # Snapshot starts empty; entities must handle None gracefully until first refresh
        self.data = CoordinatorData()

    # ------------------------------------------------------------------
    # HA entry point
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> CoordinatorData:
        """Called by HA on every update_interval tick.

        First call: runs all tiers sequentially and returns a fully
        populated snapshot (so async_config_entry_first_refresh() succeeds).

        Subsequent calls: fires due tiers as independent background tasks and
        returns the current snapshot immediately; entities receive push updates
        via async_set_updated_data() as each task completes.
        """
        try:
            await self.api.login()
        except (AuthenticationError, TokenRefreshError) as exc:
            raise UpdateFailed(f"PAJ GPS authentication failed: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"PAJ GPS connection error: {exc}") from exc

        if not self._initial_refresh_done:
            await self._run_devices_tier()
            await self._run_positions_tier()
            self._initial_refresh_done = True
            return self.data

        now = time.monotonic()

        if now - self._last_devices_fetch >= DEVICES_INTERVAL:
            self.hass.async_create_task(self._run_devices_tier())

        if now - self._last_positions_fetch >= POSITIONS_INTERVAL:
            self.hass.async_create_task(self._run_positions_tier())

        return self.data

    # ------------------------------------------------------------------
    # Tier 1 — device list
    # ------------------------------------------------------------------

    async def _run_devices_tier(self) -> None:
        """Fetch the full device list and push an updated snapshot."""
        self._last_devices_fetch = time.monotonic()
        try:
            devices = await self.api.get_devices()
        except (PajGpsApiError, Exception) as exc:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch device list: %s", exc)
            return

        new_data = dataclasses.replace(self.data, devices=devices)
        self.async_set_updated_data(new_data)

    # ------------------------------------------------------------------
    # Tier 2 — positions
    # ------------------------------------------------------------------

    async def _run_positions_tier(self) -> None:
        """Fetch all positions in one bulk request."""
        self._last_positions_fetch = time.monotonic()
        device_ids = [d.id for d in self.data.devices if d.id is not None]
        if not device_ids:
            return

        # --- bulk positions ---
        try:
            track_points = await self.api.get_all_last_positions(device_ids)
        except (PajGpsApiError, Exception) as exc:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch positions: %s", exc)
            return

        new_positions = {
            tp.iddevice: tp for tp in track_points if tp.iddevice is not None
        }
        new_data = dataclasses.replace(self.data, positions=new_positions)
        self.async_set_updated_data(new_data)

    # ------------------------------------------------------------------
    # Entity helper — device info dict
    # ------------------------------------------------------------------

    def get_device_info(self, device_id: int) -> DeviceInfo | None:
        """Return the HA DeviceInfo dict for the given device_id."""
        for device in self.data.devices:
            if device.id == device_id:
                return DeviceInfo(
                    identifiers={(DOMAIN, f"{self._entry_data['guid']}_{device_id}")},
                    name=device.name or f"PAJ GPS {device_id}",
                    manufacturer="PAJ GPS",
                    model=(
                        device.device_models[0].get("model")
                        if device.device_models
                        else None
                    )
                    or "Unknown",
                )
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """Clean up all resources owned by this coordinator."""
        await self._queue.shutdown()
        if self._owns_websession:
            await self.api.close()

    @property
    def entry_data(self) -> dict:
        """Return the config entry data."""
        return self._entry_data
