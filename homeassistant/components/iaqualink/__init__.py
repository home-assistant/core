"""Component to embed Aqualink devices."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
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
from iaqualink.exception import AqualinkServiceException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, UPDATE_INTERVAL
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

    aqualink = AqualinkClient(username, password, httpx_client=get_async_client(hass))
    try:
        await aqualink.login()
    except AqualinkServiceException as login_exception:
        _LOGGER.error("Failed to login: %s", login_exception)
        await aqualink.close()
        return False
    except (TimeoutError, httpx.HTTPError) as aio_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            f"Error while attempting login: {aio_exception}"
        ) from aio_exception

    try:
        systems = await aqualink.get_systems()
    except AqualinkServiceException as svc_exception:
        await aqualink.close()
        raise ConfigEntryNotReady(
            f"Error while attempting to retrieve systems list: {svc_exception}"
        ) from svc_exception

    systems = list(systems.values())
    if not systems:
        _LOGGER.error("No systems detected or supported")
        await aqualink.close()
        return False

    runtime_data = AqualinkRuntimeData(
        aqualink, binary_sensors=[], lights=[], sensors=[], switches=[], thermostats=[]
    )
    for system in systems:
        try:
            devices = await system.get_devices()
        except AqualinkServiceException as svc_exception:
            await aqualink.close()
            raise ConfigEntryNotReady(
                f"Error while attempting to retrieve devices list: {svc_exception}"
            ) from svc_exception

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

    async def _async_systems_update(_: datetime) -> None:
        """Refresh internal state for all systems."""
        for system in systems:
            prev = system.online

            try:
                await system.update()
            except (AqualinkServiceException, httpx.HTTPError) as svc_exception:
                if prev is not None:
                    _LOGGER.warning(
                        "Failed to refresh system %s state: %s",
                        system.serial,
                        svc_exception,
                    )
                await system.aqualink.close()
            else:
                cur = system.online
                if cur and not prev:
                    _LOGGER.warning("System %s reconnected to iAqualink", system.serial)

            async_dispatcher_send(hass, DOMAIN)

    entry.async_on_unload(
        async_track_time_interval(hass, _async_systems_update, UPDATE_INTERVAL)
    )

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
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper
