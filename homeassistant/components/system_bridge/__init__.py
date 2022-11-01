"""The System Bridge integration."""
from __future__ import annotations

import asyncio
import logging

import async_timeout
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.version import SUPPORTED_VERSION, Version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import services
from .const import DOMAIN, MODULES
from .coordinator import SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up System Bridge from a config entry."""

    # Check version before initialising
    version = Version(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    try:
        if not await version.check_supported():
            raise ConfigEntryNotReady(
                f"You are not running a supported version of System Bridge. Please update to {SUPPORTED_VERSION} or higher."
            )
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    coordinator = SystemBridgeDataUpdateCoordinator(
        hass,
        _LOGGER,
        entry=entry,
    )
    try:
        async with async_timeout.timeout(30):
            await coordinator.async_get_data(MODULES)
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    await coordinator.async_config_entry_first_refresh()

    try:
        # Wait for initial data
        async with async_timeout.timeout(30):
            while not coordinator.is_ready():
                _LOGGER.debug(
                    "Waiting for initial data from %s (%s)",
                    entry.title,
                    entry.data[CONF_HOST],
                )
                await asyncio.sleep(1)
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    _LOGGER.debug(
        "Initial coordinator data for %s (%s):\n%s",
        entry.title,
        entry.data[CONF_HOST],
        coordinator.data.json(),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    services.register(hass)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            entry.entry_id
        ]

        # Ensure disconnected and cleanup stop sub
        await coordinator.websocket_client.close()
        if coordinator.unsub:
            coordinator.unsub()

        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        services.remove(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


class SystemBridgeEntity(CoordinatorEntity[SystemBridgeDataUpdateCoordinator]):
    """Defines a base System Bridge entity."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str,
        name: str | None,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        self._hostname = coordinator.data.system.hostname
        self._key = f"{self._hostname}_{key}"
        self._name = f"{self._hostname} {name}"
        self._configuration_url = (
            f"http://{self._hostname}:{api_port}/app/settings.html"
        )
        self._mac_address = coordinator.data.system.mac_address
        self._uuid = coordinator.data.system.uuid
        self._version = coordinator.data.system.version

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this System Bridge instance."""
        return DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            identifiers={(DOMAIN, self._uuid)},
            name=self._hostname,
            sw_version=self._version,
        )
