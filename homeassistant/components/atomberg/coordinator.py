"""Data update coordinator for Atomberg."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    COMMAND_SLEEP_WINDOW,
    COMMAND_START_UTC,
    COMMAND_STOP_UTC,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_LOCK,
    DEVICE_TYPE_WATER_PURIFIER,
    AtombergAuthError,
    AtombergClient,
    AtombergConnectionError,
    AtombergDevice,
    AtombergError,
    parse_state,
)
from .const import (
    DOMAIN,
    LOCK_GUEST_PIN_VALIDITY,
    LOCK_SERIES_TIMED_PIN,
    LOGGER,
    UPDATE_INTERVAL,
)

type AtombergConfigEntry = ConfigEntry[AtombergCoordinator]


class AtombergCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the Atomberg cloud for the state of all fans on the account."""

    config_entry: AtombergConfigEntry
    devices: dict[str, AtombergDevice]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AtombergConfigEntry,
        client: AtombergClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.devices = {}
        self._pending_sleep_window: dict[str, dict[str, int]] = {}

    @override
    async def _async_setup(self) -> None:
        try:
            devices = await self.client.async_get_devices()
        except AtombergAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except AtombergError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
        self.devices = {
            device.device_id: device
            for device in devices
            if device.device_type
            in (DEVICE_TYPE_FAN, DEVICE_TYPE_WATER_PURIFIER, DEVICE_TYPE_LOCK)
        }

    def devices_of_type(self, device_type: str) -> list[AtombergDevice]:
        """Return the devices of one type."""
        return [
            device
            for device in self.devices.values()
            if device.device_type == device_type
        ]

    def supports_setting(self, device: AtombergDevice, key: str) -> bool:
        """Return whether the device accepts and reports a setting."""
        if device.supported_commands:
            return key in device.supported_commands
        return key in self.data.get(device.device_id, {})

    def sleep_window_values(self, device_id: str) -> tuple[int | None, int | None]:
        """Return the sleep window start and stop, None when never set."""
        state = self.data[device_id]
        start = state.get(COMMAND_START_UTC)
        stop = state.get(COMMAND_STOP_UTC)
        if start is None or stop is None or start % 86400 == stop % 86400:
            start = stop = None
        pending = self._pending_sleep_window.get(device_id, {})
        return pending.get(COMMAND_START_UTC, start), pending.get(
            COMMAND_STOP_UTC, stop
        )

    async def async_set_sleep_window(self, device_id: str, enabled: bool) -> None:
        """Enable or disable the daily sleep window."""
        if not enabled:
            await self.async_send_command(
                device_id, {COMMAND_SLEEP_WINDOW: 0}, {COMMAND_SLEEP_WINDOW: 0}
            )
            return
        start, stop = self.sleep_window_values(device_id)
        if start is None or stop is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="sleep_window_not_set"
            )
        command = {
            COMMAND_SLEEP_WINDOW: 1,
            COMMAND_START_UTC: start,
            COMMAND_STOP_UTC: stop,
        }
        await self.async_send_command(device_id, command, command)
        self._pending_sleep_window.pop(device_id, None)

    async def async_set_sleep_window_time(
        self, device_id: str, key: str, seconds: int
    ) -> None:
        """Set the start or stop of the sleep window."""
        self._pending_sleep_window.setdefault(device_id, {})[key] = seconds
        if self.data[device_id].get(COMMAND_SLEEP_WINDOW):
            await self.async_set_sleep_window(device_id, True)
        else:
            self.async_update_listeners()

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            states = await self.client.async_get_states()
        except AtombergAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except AtombergError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return {
            device_id: parse_state(device, states[device_id])
            for device_id, device in self.devices.items()
            if device_id in states
        }

    @staticmethod
    @contextmanager
    def _command_errors() -> Generator[None]:
        try:
            yield
        except AtombergConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except AtombergAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except AtombergError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_generate_guest_pin(self, device: AtombergDevice) -> dict[str, Any]:
        """Generate a guest PIN; some lock series get a time-limited PIN."""
        start = end = None
        if device.series == LOCK_SERIES_TIMED_PIN:
            now = dt_util.utcnow()
            start = int(now.timestamp())
            end = int((now + LOCK_GUEST_PIN_VALIDITY).timestamp())
        with self._command_errors():
            return await self.client.async_get_guest_pin(device.device_id, start, end)

    async def async_send_command(
        self, device_id: str, command: dict[str, Any], new_state: dict[str, Any]
    ) -> None:
        """Send a command and apply the expected state without polling again."""
        with self._command_errors():
            await self.client.async_send_command(device_id, command)
        self.async_set_updated_data(
            {
                **self.data,
                device_id: {**self.data[device_id], **new_state},
            }
        )
