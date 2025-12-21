"""DataUpdateCoordinator for NRGkick integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NRGkickAPI,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Type alias for typed config entry with runtime_data.
type NRGkickConfigEntry = ConfigEntry[NRGkickDataUpdateCoordinator]


class NRGkickDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching NRGkick data from the API."""

    config_entry: NRGkickConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: NRGkickAPI, entry: NRGkickConfigEntry
    ) -> None:
        """Initialize."""
        self.api = api
        self.entry = entry

        # Get scan interval from options or use default.
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
            # Data is a dict that supports __eq__ comparison.
            # Avoid unnecessary entity updates when data hasn't changed.
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            info = await self.api.get_info()
            control = await self.api.get_control()
            values = await self.api.get_values()
        except NRGkickApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except NRGkickApiClientCommunicationError as err:
            raise UpdateFailed(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err

        return {
            "info": info,
            "control": control,
            "values": values,
        }

    async def _async_execute_command_with_verification(
        self,
        command_func: Callable[[], Awaitable[dict[str, Any]]],
        expected_value: Any,
        control_key: str,
        *,
        target: str,
        value: str,
    ) -> None:
        """Execute a command and verify the state changed.

        Args:
            command_func: Async function to execute the command
            expected_value: Expected value after command execution
            control_key: Key in control data to verify (e.g., "charge_pause")
            error_message: Error message to show if verification fails

        """
        # Execute command and get response.
        try:
            response = await command_func()
        except NRGkickApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={
                    "target": target,
                    "value": value,
                    "error": str(err),
                },
            ) from err

        # Check if response contains an error message.
        if "Response" in response:
            device_error = response["Response"]
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={
                    "target": target,
                    "value": value,
                    "error": str(device_error),
                },
            )

        # Check if response contains the expected key with the new value.
        if control_key in response:
            actual_value = response[control_key]

            # Convert both values to float for comparison to handle type differences.
            try:
                actual_float = float(actual_value) if actual_value is not None else None
                expected_float = (
                    float(expected_value) if expected_value is not None else None
                )
                if actual_float != expected_float:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="set_failed_unexpected_value",
                        translation_placeholders={
                            "target": target,
                            "value": value,
                            "actual": str(actual_value),
                            "expected": str(expected_value),
                        },
                    )
            except (ValueError, TypeError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_failed_invalid_value",
                    translation_placeholders={
                        "target": target,
                        "value": value,
                    },
                ) from err

            # Update coordinator data immediately with the new value.
            if "control" not in self.data:
                self.data["control"] = {}
            self.data["control"][control_key] = actual_value

            # Notify all entities that coordinator data has been updated.
            self.async_set_updated_data(self.data)

        else:
            # Response doesn't contain expected key - refresh to get current state.
            await asyncio.sleep(2)
            await self.async_request_refresh()

    async def async_set_current(self, current: float) -> None:
        """Set the charging current."""
        await self._async_execute_command_with_verification(
            lambda: self.api.set_current(current),
            current,
            "current_set",
            target="current_set",
            value=str(current),
        )

    async def async_set_charge_pause(self, pause: bool) -> None:
        """Set the charge pause state."""
        expected_state = 1 if pause else 0
        await self._async_execute_command_with_verification(
            lambda: self.api.set_charge_pause(pause),
            expected_state,
            "charge_pause",
            target="charge_pause",
            value="on" if pause else "off",
        )

    async def async_set_energy_limit(self, energy_limit: int) -> None:
        """Set the energy limit."""
        await self._async_execute_command_with_verification(
            lambda: self.api.set_energy_limit(energy_limit),
            energy_limit,
            "energy_limit",
            target="energy_limit",
            value=str(energy_limit),
        )

    async def async_set_phase_count(self, phase_count: int) -> None:
        """Set the phase count."""
        await self._async_execute_command_with_verification(
            lambda: self.api.set_phase_count(phase_count),
            phase_count,
            "phase_count",
            target="phase_count",
            value=str(phase_count),
        )
