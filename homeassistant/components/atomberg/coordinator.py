"""Data update coordinator for Atomberg."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, override

from atomberg_api import (
    DEVICE_TYPE_FAN,
    AtombergAuthError,
    AtombergClient,
    AtombergConnectionError,
    AtombergDevice,
    AtombergError,
    parse_state,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

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
            if device.device_type == DEVICE_TYPE_FAN
        }

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

    async def async_send_command(
        self, device_id: str, command: dict[str, Any], new_state: dict[str, Any]
    ) -> None:
        """Send a command and apply the expected state without polling again."""
        with self._command_errors():
            await self.client.async_send_command(device_id, command)
        self.data = {
            **self.data,
            device_id: {**self.data[device_id], **new_state},
        }
        self.async_update_listeners()
