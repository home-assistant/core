"""Component to embed Aqualink devices."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
import logging
from typing import Any, Concatenate

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkLight,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import DOMAIN
from .coordinator import AqualinkDataUpdateCoordinator
from .entity import AqualinkEntity

_LOGGER = logging.getLogger(__name__)

ATTR_CONFIG = "config"
PARALLEL_UPDATES = 0

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type AqualinkConfigEntry = ConfigEntry[AqualinkRuntimeData]


@dataclass
class AqualinkRuntimeData:
    """Runtime data for Aqualink."""

    client: AqualinkClient
    coordinators: dict[str, AqualinkDataUpdateCoordinator]
    # These will contain the initialized devices
    binary_sensors: list[AqualinkBinarySensor]
    lights: list[AqualinkLight]
    sensors: list[AqualinkSensor]
    switches: list[AqualinkSwitch]
    thermostats: list[AqualinkThermostat]


async def async_setup_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> bool:
    """Set up Aqualink from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    aqualink = AqualinkClient(
        username,
        password,
        httpx_client=get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2),
    )
    try:
        await aqualink.login()
    except AqualinkServiceUnauthorizedException as auth_exception:
        await aqualink.close()
        raise ConfigEntryAuthFailed(
            "Invalid credentials for iAqualink"
        ) from auth_exception
    except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as aio_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            f"Error while attempting login: {aio_exception}"
        ) from aio_exception

    try:
        systems = await aqualink.get_systems()
    except AqualinkServiceUnauthorizedException as auth_exception:
        await aqualink.close()
        raise ConfigEntryAuthFailed(
            "Invalid credentials for iAqualink"
        ) from auth_exception
    except AqualinkServiceException as svc_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            f"Error while attempting to retrieve systems list: {svc_exception}"
        ) from svc_exception

    systems_list = list(systems.values())
    if not systems_list:
        await aqualink.close()
        raise ConfigEntryError("No systems detected or supported")

    runtime_data = AqualinkRuntimeData(
        aqualink,
        coordinators={},
        binary_sensors=[],
        lights=[],
        sensors=[],
        switches=[],
        thermostats=[],
    )
    for system in systems_list:
        coordinator = AqualinkDataUpdateCoordinator(hass, entry, system)
        runtime_data.coordinators[system.serial] = coordinator
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryAuthFailed:
            await aqualink.close()
            raise

        try:
            devices = await system.get_devices()
        except AqualinkServiceUnauthorizedException as auth_exception:
            await aqualink.close()
            raise ConfigEntryAuthFailed(
                "Invalid credentials for iAqualink"
            ) from auth_exception
        except AqualinkServiceException as svc_exception:
            await aqualink.close()
            raise ConfigEntryNotReady(
                f"Error while attempting to retrieve devices list: {svc_exception}"
            ) from svc_exception

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            name=system.name,
            identifiers={(DOMAIN, system.serial)},
            manufacturer="Jandy",
            serial_number=system.serial,
        )

        for dev in devices.values():
            if isinstance(dev, AqualinkThermostat):
                runtime_data.thermostats += [dev]
            elif isinstance(dev, AqualinkLight):
                runtime_data.lights += [dev]
            elif isinstance(dev, AqualinkSwitch):
                runtime_data.switches += [dev]
            elif isinstance(dev, AqualinkBinarySensor):
                runtime_data.binary_sensors += [dev]
            elif isinstance(dev, AqualinkSensor):
                runtime_data.sensors += [dev]

    _LOGGER.debug(
        "Got %s binary sensors: %s",
        len(runtime_data.binary_sensors),
        runtime_data.binary_sensors,
    )
    _LOGGER.debug("Got %s lights: %s", len(runtime_data.lights), runtime_data.lights)
    _LOGGER.debug("Got %s sensors: %s", len(runtime_data.sensors), runtime_data.sensors)
    _LOGGER.debug(
        "Got %s switches: %s", len(runtime_data.switches), runtime_data.switches
    )
    _LOGGER.debug(
        "Got %s thermostats: %s",
        len(runtime_data.thermostats),
        runtime_data.thermostats,
    )

    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AqualinkConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.client.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def refresh_system[_AqualinkEntityT: AqualinkEntity, **_P](
    func: Callable[Concatenate[_AqualinkEntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_AqualinkEntityT, _P], Coroutine[Any, Any, None]]:
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(
        self: _AqualinkEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        """Call decorated function and send update signal to all entities."""
        await func(self, *args, **kwargs)
        self.coordinator.async_update_listeners()

    return wrapper
