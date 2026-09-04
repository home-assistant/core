"""DataUpdateCoordinator for the Tewke integration."""

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, TypedDict, override

from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidResponseError,
    PyTewkeUnknownError,
)

from homeassistant.core import HassJob, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DISPATCHER_ADD_SCENES, DOMAIN, LOGGER
from .util import async_setup_observe

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime
    import logging

    from pytewke.data import (
        ConfigData,
        EnergyData,
        EnergyOverrideData,
        RadarData,
        Scene,
        SensorData,
        Target,
    )

    from homeassistant.core import HomeAssistant

    from .data import TewkeConfigEntry

# Transient errors that are worth retrying (device/network busy or timed out).
# PyTewkeInvalidResponseError is intentionally excluded — it means the device
# returned malformed data, which retrying is unlikely to fix.
_RETRYABLE_ERRORS = (PyTewkeCoapError, PyTewkeUnknownError, TimeoutError)

# Delay sequence (seconds) between successive retry attempts.
_RETRY_DELAYS: list[float] = [1.0, 2.0, 4.0]

# Seconds of observation silence before we treat the connection as lost.
_OBSERVATION_TIMEOUT_SECS = 30

# Fallback polling interval.  The coordinator is primarily push-based; this
# acts as a safety-net so that if observations go silent the coordinator can
# still recover without requiring a restart.
_RECOVERY_INTERVAL = timedelta(minutes=5)


async def _fetch_with_retries[T](fn: Callable[[], Awaitable[T]]) -> T:
    """Await *fn()*, retrying on transient errors with exponential back-off.

    Raises the original exception if all attempts are exhausted, or immediately
    if the error is not considered transient.
    """
    last_err: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            return await fn()
        except _RETRYABLE_ERRORS as err:
            last_err = err
            if attempt < len(_RETRY_DELAYS) - 1:
                LOGGER.debug(
                    "Transient Tap error (attempt %d/%d), retrying in %.0fs: %s",
                    attempt + 1,
                    len(_RETRY_DELAYS),
                    delay,
                    err,
                )
                await asyncio.sleep(delay)
        except PyTewkeInvalidResponseError, Exception:
            # Non-transient or unexpected error — fail immediately.
            raise

    assert last_err is not None
    raise last_err


class TewkeCoordinatorData(TypedDict):
    """Typed data held by TewkeCoordinator."""

    scenes: dict[str, Scene]
    targets: dict[int, Target]
    sensors: SensorData | None
    radar: RadarData | None
    energy: EnergyData | None
    energy_override: EnergyOverrideData | None
    config: ConfigData


class TewkeCoordinator(DataUpdateCoordinator[TewkeCoordinatorData]):
    """Coordinator for all Tewke state (scenes, targets, sensors).

    Updates are primarily push-based via CoAP observation callbacks registered
    in `async_setup_entry`.  `_async_update_data` runs at initial setup and on
    the periodic fallback interval (`_RECOVERY_INTERVAL`), but skips the manual
    fetch if observations are already active and data is populated — observations
    keep the data current.  The full fetch only runs when data is absent (first
    boot) or observations have gone silent.

    See TewkeCoordinatorData for the full shape of the coordinator data.
    """

    config_entry: TewkeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        config_entry: TewkeConfigEntry,
    ) -> None:
        """Initialise coordinator with a fallback recovery interval."""
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=_RECOVERY_INTERVAL,
            config_entry=config_entry,
        )
        self._observe_setup_lock = asyncio.Lock()
        self._observe_retry_task: asyncio.Task[None] | None = None
        self._observation_timeout_unsub: Callable[[], None] | None = None
        self._observation_timeout_job = HassJob(
            self._handle_observation_timeout, cancel_on_shutdown=True
        )

    def reset_observation_timeout(self) -> None:
        """Restart the inactivity timer; call this on every received observation.

        Runs on the event loop (CoAP callbacks are async), so async_call_later
        is safe to use directly — no call_soon_threadsafe required.
        """
        if self._observation_timeout_unsub is not None:
            self._observation_timeout_unsub()
        self._observation_timeout_unsub = async_call_later(
            self.hass, _OBSERVATION_TIMEOUT_SECS, self._observation_timeout_job
        )

    def cancel_observation_timeout(self) -> None:
        """Cancel the pending inactivity timer and any in-flight retry task.

        Called on entry unload to prevent the retry task from running against
        stale runtime_data after the entry has been torn down.
        """
        if self._observation_timeout_unsub is not None:
            self._observation_timeout_unsub()
            self._observation_timeout_unsub = None
        if self._observe_retry_task is not None and not self._observe_retry_task.done():
            self._observe_retry_task.cancel()
            self._observe_retry_task = None

    @callback
    def _handle_observation_timeout(self, _now: datetime) -> None:
        """Fire on the event loop when no observations have arrived for a while."""
        self.logger.info(
            "Observations timed out for tap %s, retrying",
            self.config_entry.runtime_data.tap.wall_dock_id,
        )
        self._observation_timeout_unsub = None
        self.config_entry.runtime_data.observe_active = False
        if self._observe_retry_task is not None and not self._observe_retry_task.done():
            return

        _observe_delays: list[int] = [30, 60, 90]
        max_fails = len(_observe_delays)

        async def _do_retry_attempt(attempt_num: int) -> bool:
            if attempt_num != 0:
                return await self._setup_observe()

            if not await self.config_entry.runtime_data.tap.retry_observes():
                return False

            self.config_entry.runtime_data.observe_active = True
            self.reset_observation_timeout()
            return True

        async def _retry() -> None:
            failed = 0

            for attempt, delay in enumerate(_observe_delays):
                if await _do_retry_attempt(attempt):
                    break

                self.logger.warning("Failed to retry observe")
                failed += 1
                if attempt < len(_observe_delays) - 1:
                    await asyncio.sleep(delay)

            # Tell HomeAssistant that the device is offline
            # If failed is ever higher than 3, reality has broken, handle regardless
            if failed >= max_fails:
                self.async_set_update_error(
                    UpdateFailed(
                        f"Failed to re-initialise observations with tap "
                        f"{self.config_entry.runtime_data.tap.wall_dock_id} "
                        f"after {failed} attempts"
                    )
                )

            if self._observe_retry_task is asyncio.current_task():
                self._observe_retry_task = None

        self._observe_retry_task = self.hass.async_create_task(_retry())
        if self._observe_retry_task.done():
            self._observe_retry_task = None

    async def _setup_observe(self) -> bool:
        async with self._observe_setup_lock:
            if self.config_entry.runtime_data.observe_active:
                return True
            LOGGER.info(
                "CoAP observations not active for %s; attempting to re-establish",
                self.config_entry.entry_id,
            )
            return await async_setup_observe(self, self.hass, self.config_entry)

    @override
    async def _async_update_data(self) -> TewkeCoordinatorData:
        """Fetch current state for all resources, retrying on transient errors.

        If CoAP observations are active and we already have data, skip the
        manual fetch entirely — observations will keep the data current.
        The full fetch only runs when we have no data yet (initial startup)
        or when observations are down and we need to fall back to polling.
        """
        if self.config_entry.runtime_data.observe_active and self.data is not None:
            return self.data

        tap = self.config_entry.runtime_data.tap
        expected_dock_id = self.config_entry.unique_id

        if tap.wall_dock_id != expected_dock_id:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_swap",
                translation_placeholders={
                    "expected_dock_id": str(expected_dock_id),
                    "reported_dock_id": str(tap.wall_dock_id),
                },
            )

        try:
            scenes = await _fetch_with_retries(tap.get_scenes)
            targets = await _fetch_with_retries(tap.get_targets)
            config = await _fetch_with_retries(tap.get_config)
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        try:
            sensors: SensorData | None = await tap.get_sensors()
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            LOGGER.debug("Sensor data not available from Tewke Tap: %s", err)
            sensors = None

        try:
            radar: RadarData | None = await tap.get_radar()
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            LOGGER.debug("Radar data not available from Tewke Tap: %s", err)
            radar = None

        try:
            energy: EnergyData | None = await tap.get_energy()
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            LOGGER.debug("Energy data not available from Tewke Tap: %s", err)
            energy = None

        try:
            energy_override: EnergyOverrideData | None = await tap.get_energy_override()
        except (
            PyTewkeCoapError,
            PyTewkeInvalidResponseError,
            PyTewkeUnknownError,
            TimeoutError,
        ) as err:
            LOGGER.debug("Energy override data not available from Tewke Tap: %s", err)
            energy_override = None

        if self.data is not None:
            current_scenes = self.data["scenes"]
            new_scenes = {
                scene_id: scene
                for scene_id, scene in scenes.items()
                if scene_id not in current_scenes
            }
            if new_scenes:
                LOGGER.info(
                    "Discovered new scenes during polling, automatically adding: %s",
                    new_scenes,
                )
                self.hass.loop.call_soon(
                    async_dispatcher_send,
                    self.hass,
                    f"{DISPATCHER_ADD_SCENES}_{self.config_entry.entry_id}",
                    list(new_scenes.values()),
                )

        new_data = TewkeCoordinatorData(
            scenes=dict(scenes),
            targets=targets,
            sensors=sensors,
            radar=radar,
            energy=energy,
            energy_override=energy_override,
            config=config,
        )

        self.data = new_data

        try:
            await self._setup_observe()
        except Exception as err:
            raise UpdateFailed from err

        return new_data
