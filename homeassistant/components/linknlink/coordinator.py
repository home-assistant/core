"""LinknLink Coordinator."""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import logging
from typing import Any

import linknlink as llk
from linknlink.exceptions import (
    AuthenticationError,
    LinknLinkException,
    NetworkTimeoutError,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DEFAULT_PORT, DOMAIN, DOMAINS_AND_TYPES

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 10


class Coordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    api: llk.Device

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize the data service."""
        super().__init__(
            hass,
            _LOGGER,
            name=config.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.hass = hass
        self.config = config
        self.fw_version: int | None = None
        self.authorized: bool | None = None
        self.reset_jobs: list[CALLBACK_TYPE] = []

    @property
    def available(self) -> bool | None:
        """Return True if the device is available."""
        return self.api.auth()

    def unload(self) -> None:
        """Cancel jobs."""
        while self.reset_jobs:
            self.reset_jobs.pop()()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api.mac.hex())},
            name=self.config.title,
            manufacturer=self.api.manufacturer,
            model=self.api.model,
            sw_version=str(self.fw_version),
        )

    @staticmethod
    async def async_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Update the device and related entities.

        Triggered when the device is renamed on the frontend.
        """
        device_registry = dr.async_get(hass)
        assert entry.unique_id
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.unique_id)}
        )
        assert device_entry
        device_registry.async_update_device(device_entry.id, name=entry.title)
        await hass.config_entries.async_reload(entry.entry_id)

    def _get_firmware_version(self) -> int | None:
        """Get firmware version."""
        self.api.auth()
        with suppress(LinknLinkException, OSError):
            return self.api.get_fwversion()
        return None

    async def async_setup(self) -> bool:
        """Set up the device and related entities."""
        config = self.config

        api = llk.gendevice(
            config.data[CONF_TYPE],
            (config.data[CONF_HOST], DEFAULT_PORT),
            bytes.fromhex(config.data[CONF_MAC]),
            name=config.title,
        )
        api.timeout = config.data[CONF_TIMEOUT]
        self.api = api
        try:
            self.fw_version = await self.hass.async_add_executor_job(
                self._get_firmware_version
            )

        except AuthenticationError:
            await self._async_handle_auth_error()
            return False

        except (NetworkTimeoutError, OSError) as err:
            _LOGGER.error("Failed to connect to the device [%s]: %s", api.host[0], err)
            raise ConfigEntryNotReady from err

        except LinknLinkException as err:
            _LOGGER.error(
                "Failed to authenticate to the device at %s: %s", api.host[0], err
            )
            return False

        self.authorized = True
        self.reset_jobs.append(config.add_update_listener(self.async_update))

        return True

    async def _async_handle_auth_error(self) -> None:
        """Handle an authentication error."""
        if self.authorized is False:
            return

        self.authorized = False

        _LOGGER.error(
            (
                "%s (%s at %s) is locked. Click Configuration in the sidebar, "
                "click Integrations, click Configure on the device and follow "
                "the instructions to unlock it"
            ),
            self.name,
            self.api.model,
            self.api.host[0],
        )

        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH},
                data={CONF_NAME: self.name, **self.config.data},
            )
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        if (
            self.api.type in DOMAINS_AND_TYPES[Platform.SENSOR]
            or self.api.type in DOMAINS_AND_TYPES[Platform.BINARY_SENSOR]
        ):
            data = self.api.check_sensors()
            return data
        return {}


class LinknLinkEntity(CoordinatorEntity[Coordinator]):
    """LinknLinkEntity - In charge of get the data for a site."""

    def __init__(self, coordinator: Coordinator, context: Any = None) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)
        self._attr_device_info = coordinator.device_info
