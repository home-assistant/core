"""Coordinator for PTDevices integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

import aioptdevices
from aioptdevices.interface import Interface, PTDevicesResponseData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REFRESH_COOLDOWN: Final = 30
UPDATE_INTERVAL = timedelta(seconds=60)

type PTDevicesConfigEntry = ConfigEntry[PTDevicesCoordinator]


class PTDevicesCoordinator(DataUpdateCoordinator[PTDevicesResponseData]):
    """Class for interacting with PTDevices get_data."""

    config_entry: PTDevicesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PTDevicesConfigEntry,
        ptdevices_interface: Interface,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
                cooldown=REFRESH_COOLDOWN,
            ),
        )

        self.interface = ptdevices_interface
        self.previous_devices: set[str] = set()

    async def _async_update_data(self) -> PTDevicesResponseData:
        try:
            data = await self.interface.get_data()
        except aioptdevices.PTDevicesRequestError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_access_token",
                translation_placeholders={"error": repr(err)},
            ) from err
        except aioptdevices.PTDevicesForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

        # Remove stale devices
        current_devices = set(data["body"].keys())
        if stale_devices := self.previous_devices - current_devices:
            device_registry = dr.async_get(self.hass)
            for device_id in stale_devices:
                # Remove the device from the device registry
                stale_device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if stale_device:
                    device_registry.async_update_device(
                        device_id=stale_device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        return data["body"]
