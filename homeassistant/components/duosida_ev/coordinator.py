"""Data update coordinator for Duosida EV Charger."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from duosida_ev import DuosidaCharger

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

# Connection retry settings
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0
MAX_RETRY_DELAY = 10.0

_LOGGER = logging.getLogger(__name__)

# Storage version - increment if storage format changes
STORAGE_VERSION = 1


class DuosidaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Duosida data."""

    def __init__(
        self,
        hass: HomeAssistant,
        charger: DuosidaCharger,
        device_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

        self.charger = charger
        self._device_id = device_id

        # Storage for persisting settings that charger doesn't report back
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{device_id}",
        )

        # Settings the charger doesn't report back (stored when user sets them)
        self._stored_settings: dict[str, Any] = {
            "max_current": None,
            "led_brightness": None,
            "direct_mode": None,
            "stop_on_disconnect": None,
            "max_voltage": None,
            "min_voltage": None,
            "total_energy": 0.0,
            "last_power": 0.0,
            "last_update_time": None,
        }

        # Track if settings have been synced this session
        self._settings_synced_this_session = False

    async def async_load_stored_settings(self) -> None:
        """Load stored settings from Home Assistant storage."""
        stored = await self._store.async_load()

        if stored:
            _LOGGER.debug("Loaded stored settings: %s", stored)
            self._stored_settings.update(stored)
        else:
            _LOGGER.debug("No stored settings found, using defaults")

    async def _async_save_stored_settings(self) -> None:
        """Save current settings to Home Assistant storage."""
        await self._store.async_save(self._stored_settings)
        _LOGGER.debug("Saved settings to storage: %s", self._stored_settings)

    async def _async_sync_settings_to_charger(self) -> None:
        """Sync user-configured settings to the charger on first connection."""
        settings_to_sync = []

        max_current = self._stored_settings.get("max_current")
        if max_current is not None:
            settings_to_sync.append(f"max current: {max_current}A")
            await self.hass.async_add_executor_job(
                self.charger.set_max_current, max_current
            )

        led_brightness = self._stored_settings.get("led_brightness")
        if led_brightness is not None:
            settings_to_sync.append(f"LED brightness: {led_brightness}")
            await self.hass.async_add_executor_job(
                self.charger.set_led_brightness, led_brightness
            )

        direct_mode = self._stored_settings.get("direct_mode")
        if direct_mode is not None:
            settings_to_sync.append(f"direct mode: {direct_mode}")
            await self.hass.async_add_executor_job(
                self.charger.set_direct_work_mode, direct_mode
            )

        stop_on_disconnect = self._stored_settings.get("stop_on_disconnect")
        if stop_on_disconnect is not None:
            settings_to_sync.append(f"stop on disconnect: {stop_on_disconnect}")
            await self.hass.async_add_executor_job(
                self.charger.set_stop_on_disconnect, stop_on_disconnect
            )

        max_voltage = self._stored_settings.get("max_voltage")
        if max_voltage is not None:
            settings_to_sync.append(f"max voltage: {max_voltage}V")
            await self.hass.async_add_executor_job(
                self.charger.set_max_voltage, max_voltage
            )

        min_voltage = self._stored_settings.get("min_voltage")
        if min_voltage is not None:
            settings_to_sync.append(f"min voltage: {min_voltage}V")
            await self.hass.async_add_executor_job(
                self.charger.set_min_voltage, min_voltage
            )

        if settings_to_sync:
            _LOGGER.info(
                "Synced user-configured settings to charger: %s",
                ", ".join(settings_to_sync),
            )
        else:
            _LOGGER.debug("No user-configured settings to sync")

    def get_stored_setting(self, key: str) -> Any:
        """Get a stored setting value."""
        return self._stored_settings.get(key)

    async def _async_connect_with_retry(self) -> bool:
        """Connect to charger with exponential backoff retry logic."""
        import asyncio

        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                _LOGGER.debug(
                    "Connection attempt %d/%d to charger at %s",
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    self.charger.host,
                )

                connected = await self.hass.async_add_executor_job(self.charger.connect)

                if connected:
                    if attempt > 1:
                        _LOGGER.info(
                            "Successfully connected to charger on attempt %d/%d",
                            attempt,
                            MAX_RETRY_ATTEMPTS,
                        )
                    return True

                # Connection failed, prepare for retry
                if attempt < MAX_RETRY_ATTEMPTS:
                    _LOGGER.warning(
                        "Connection attempt %d/%d failed, retrying in %.1fs",
                        attempt,
                        MAX_RETRY_ATTEMPTS,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)

                    # Exponential backoff with cap
                    retry_delay = min(
                        retry_delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY
                    )
                else:
                    _LOGGER.error(
                        "All %d connection attempts failed", MAX_RETRY_ATTEMPTS
                    )

            except Exception as err:
                _LOGGER.debug(
                    "Connection attempt %d/%d raised exception: %s",
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    err,
                )

                if attempt < MAX_RETRY_ATTEMPTS:
                    _LOGGER.warning(
                        "Connection error on attempt %d/%d, retrying in %.1fs: %s",
                        attempt,
                        MAX_RETRY_ATTEMPTS,
                        retry_delay,
                        err,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY
                    )
                else:
                    _LOGGER.error(
                        "Connection failed after %d attempts: %s",
                        MAX_RETRY_ATTEMPTS,
                        err,
                    )

        return False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the charger."""
        try:
            connected = await self._async_connect_with_retry()

            if not connected:
                raise UpdateFailed(
                    f"Failed to connect to charger after {MAX_RETRY_ATTEMPTS} attempts"
                )

            try:
                import asyncio

                await asyncio.sleep(0.3)

                if not self._settings_synced_this_session:
                    await self._async_sync_settings_to_charger()
                    self._settings_synced_this_session = True

                status = await self.hass.async_add_executor_job(self.charger.get_status)

                if not status:
                    raise UpdateFailed("Failed to get status from charger")

                data = status.to_dict()
                _LOGGER.debug(
                    "Got status: state=%s, voltage=%.1fV, current=%.2fA, power=%.0fW",
                    data.get("state"),
                    data.get("voltage", 0),
                    data.get("current", 0),
                    data.get("power", 0),
                )

                # Integrate power over time to calculate total energy
                current_power = data.get("power", 0.0) or 0.0
                current_time = self.hass.loop.time()

                last_power = self._stored_settings.get("last_power", 0.0) or 0.0
                last_time = self._stored_settings.get("last_update_time")
                total_energy = self._stored_settings.get("total_energy", 0.0) or 0.0

                if last_time is not None and current_time > last_time:
                    time_delta_hours = (current_time - last_time) / 3600.0
                    average_power = (current_power + last_power) / 2.0
                    energy_delta = (average_power * time_delta_hours) / 1000.0

                    if 0 < energy_delta < 100:
                        total_energy += energy_delta

                self._stored_settings["total_energy"] = total_energy
                self._stored_settings["last_power"] = current_power
                self._stored_settings["last_update_time"] = current_time

                self.hass.async_create_task(self._async_save_stored_settings())

                data["total_energy"] = total_energy

                return data

            finally:
                await self.hass.async_add_executor_job(self.charger.disconnect)

        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("Error communicating with charger: %s", err)
            raise UpdateFailed(f"Error communicating with charger: {err}") from err

    async def _async_send_command(
        self, command_func: Callable[[], bool], command_name: str
    ) -> bool:
        """Send a command to the charger with connect/disconnect."""
        try:
            _LOGGER.debug("Sending %s command", command_name)

            connected = await self._async_connect_with_retry()
            if not connected:
                _LOGGER.error("Failed to connect for %s", command_name)
                return False

            try:
                import asyncio

                await asyncio.sleep(0.3)
                return await self.hass.async_add_executor_job(command_func)
            finally:
                await self.hass.async_add_executor_job(self.charger.disconnect)

        except Exception as err:
            _LOGGER.error("Error in %s: %s", command_name, err)
            return False

    async def async_start_charging(self) -> bool:
        """Start charging the vehicle."""
        result = await self._async_send_command(
            self.charger.start_charging, "start charging"
        )

        if result:
            # Wait for charger to update state, then refresh
            import asyncio

            await asyncio.sleep(1.0)
            await self.async_request_refresh()

        return result

    async def async_stop_charging(self) -> bool:
        """Stop charging the vehicle."""
        result = await self._async_send_command(
            self.charger.stop_charging, "stop charging"
        )

        if result:
            import asyncio

            await asyncio.sleep(1.0)
            await self.async_request_refresh()

        return result

    async def async_set_max_current(self, current: int) -> bool:
        """Set the maximum charging current."""
        from functools import partial

        result = await self._async_send_command(
            partial(self.charger.set_max_current, current),
            f"set max current to {current}A",
        )

        if result:
            self._stored_settings["max_current"] = current
            await self._async_save_stored_settings()

            import asyncio

            await asyncio.sleep(0.5)
            await self.async_request_refresh()

        return result

    async def async_set_led_brightness(self, level: int) -> bool:
        """Set LED/screen brightness level."""
        from functools import partial

        result = await self._async_send_command(
            partial(self.charger.set_led_brightness, level),
            f"set LED brightness to {level}",
        )

        if result:
            self._stored_settings["led_brightness"] = level
            await self._async_save_stored_settings()

        return result

    async def async_set_direct_mode(self, enabled: bool) -> bool:
        """Set direct work mode (plug and charge)."""
        from functools import partial

        state = "enabled" if enabled else "disabled"
        result = await self._async_send_command(
            partial(self.charger.set_direct_work_mode, enabled),
            f"set direct mode to {state}",
        )

        if result:
            self._stored_settings["direct_mode"] = enabled
            await self._async_save_stored_settings()

        return result

    async def async_set_stop_on_disconnect(self, enabled: bool) -> bool:
        """Set whether to stop transaction when EV side disconnects."""
        from functools import partial

        state = "enabled" if enabled else "disabled"
        result = await self._async_send_command(
            partial(self.charger.set_stop_on_disconnect, enabled),
            f"set stop on disconnect to {state}",
        )

        if result:
            self._stored_settings["stop_on_disconnect"] = enabled
            await self._async_save_stored_settings()

        return result

    async def async_set_max_voltage(self, voltage: int) -> bool:
        """Set maximum working voltage."""
        from functools import partial

        result = await self._async_send_command(
            partial(self.charger.set_max_voltage, voltage),
            f"set max voltage to {voltage}V",
        )

        if result:
            self._stored_settings["max_voltage"] = voltage
            await self._async_save_stored_settings()

        return result

    async def async_set_min_voltage(self, voltage: int) -> bool:
        """Set minimum working voltage."""
        from functools import partial

        result = await self._async_send_command(
            partial(self.charger.set_min_voltage, voltage),
            f"set min voltage to {voltage}V",
        )

        if result:
            self._stored_settings["min_voltage"] = voltage
            await self._async_save_stored_settings()

        return result

    async def async_reset_total_energy(self) -> None:
        """Reset the total energy counter to zero."""
        _LOGGER.info("Resetting total energy counter")
        self._stored_settings["total_energy"] = 0.0
        self._stored_settings["last_power"] = 0.0
        self._stored_settings["last_update_time"] = None
        await self._async_save_stored_settings()
        await self.async_request_refresh()

    def disconnect(self) -> None:
        """Disconnect from the charger."""
