"""DataUpdateCoordinator for Sharp COCORO Air."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import dataclasses
import logging
from typing import Any

from aiosharp_cocoro_air import (
    Device,
    SharpApiError,
    SharpAuthError,
    SharpCOCOROAir,
    SharpConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, OPERATION_MODES, SCAN_INTERVAL

STARTUP_RETRIES = 3
STARTUP_RETRY_DELAY = 10

_LOGGER = logging.getLogger(__name__)


class SharpCocoroAirCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Coordinator that polls Sharp cloud API for device data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        session = async_get_clientsession(hass)
        self.api = SharpCOCOROAir(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
            session=session,
        )

    async def _async_setup(self) -> None:
        """Perform initial login sequence.

        Retries on transient connection errors during HA startup when
        DNS/network may not be ready yet.
        """
        last_err: Exception | None = None
        for attempt in range(1, STARTUP_RETRIES + 1):
            try:
                await self.api.authenticate()
            except SharpAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            except (SharpConnectionError, SharpApiError) as err:
                last_err = err
                if attempt < STARTUP_RETRIES:
                    _LOGGER.warning(
                        "Cloud init attempt %d/%d failed: %s, retrying in %ds",
                        attempt,
                        STARTUP_RETRIES,
                        err,
                        STARTUP_RETRY_DELAY,
                    )
                    await asyncio.sleep(STARTUP_RETRY_DELAY)
            else:
                return
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(last_err)},
        ) from last_err

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch device data from Sharp cloud API."""
        try:
            devices = await self.api.get_devices()
        except SharpAuthError:
            # Session expired -- attempt automatic re-login
            _LOGGER.info("Session expired, attempting re-login")
            try:
                await self.api.authenticate()
                devices = await self.api.get_devices()
            except SharpAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="relogin_failed",
                ) from err
            except (SharpConnectionError, SharpApiError) as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"error": str(err)},
                ) from err
        except (SharpConnectionError, SharpApiError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        return {dev.device_id: dev for dev in devices}

    async def _async_control(
        self, fn: Callable[..., Coroutine[Any, Any, None]], *args: Any
    ) -> None:
        """Run a control command with error handling."""
        try:
            await fn(*args)
        except SharpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except (SharpConnectionError, SharpApiError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    def _optimistic_update(self, device_id: str, **props) -> None:
        """Apply optimistic state update and notify entities immediately.

        The cloud API has a delay before reflecting state changes,
        so we update coordinator.data with the expected values using
        dataclasses.replace() on frozen Device/DeviceProperties instances.
        """
        if not self.data:
            return
        data = dict(self.data)
        if device_id in data:
            old = data[device_id]
            new_props = dataclasses.replace(old.properties, **props)
            data[device_id] = dataclasses.replace(old, properties=new_props)
            self.async_set_updated_data(data)

    async def async_power_on(self, device: Device) -> None:
        """Turn device on."""
        await self._async_control(self.api.power_on, device)
        self._optimistic_update(device.device_id, power="on")

    async def async_power_off(self, device: Device) -> None:
        """Turn device off."""
        await self._async_control(self.api.power_off, device)
        self._optimistic_update(device.device_id, power="off")

    async def async_set_mode(self, device: Device, mode: str) -> None:
        """Set operation mode."""
        await self._async_control(self.api.set_mode, device, mode)
        display = OPERATION_MODES.get(mode, mode)
        self._optimistic_update(device.device_id, operation_mode=display)

    async def async_set_humidify(self, device: Device, on: bool) -> None:
        """Toggle humidification."""
        await self._async_control(self.api.set_humidify, device, on)
        self._optimistic_update(device.device_id, humidify=on)
