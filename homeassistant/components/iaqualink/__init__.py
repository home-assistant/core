"""Component to embed Aqualink devices."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLight,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.exception import AqualinkServiceException

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, UPDATE_INTERVAL

_AqualinkEntityT = TypeVar("_AqualinkEntityT", bound="AqualinkEntity")
_P = ParamSpec("_P")

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


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Aqualink from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    hass.data.setdefault(DOMAIN, {})

    # These will contain the initialized devices
    binary_sensors = hass.data[DOMAIN][BINARY_SENSOR_DOMAIN] = []
    climates = hass.data[DOMAIN][CLIMATE_DOMAIN] = []
    lights = hass.data[DOMAIN][LIGHT_DOMAIN] = []
    sensors = hass.data[DOMAIN][SENSOR_DOMAIN] = []
    switches = hass.data[DOMAIN][SWITCH_DOMAIN] = []

    aqualink = AqualinkClient(username, password)
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
                climates += [dev]
            elif isinstance(dev, AqualinkLight):
                lights += [dev]
            elif isinstance(dev, AqualinkSwitch):
                switches += [dev]
            elif isinstance(dev, AqualinkBinarySensor):
                binary_sensors += [dev]
            elif isinstance(dev, AqualinkSensor):
                sensors += [dev]

    platforms = []
    if binary_sensors:
        _LOGGER.debug("Got %s binary sensors: %s", len(binary_sensors), binary_sensors)
        platforms.append(Platform.BINARY_SENSOR)
    if climates:
        _LOGGER.debug("Got %s climates: %s", len(climates), climates)
        platforms.append(Platform.CLIMATE)
    if lights:
        _LOGGER.debug("Got %s lights: %s", len(lights), lights)
        platforms.append(Platform.LIGHT)
    if sensors:
        _LOGGER.debug("Got %s sensors: %s", len(sensors), sensors)
        platforms.append(Platform.SENSOR)
    if switches:
        _LOGGER.debug("Got %s switches: %s", len(switches), switches)
        platforms.append(Platform.SWITCH)

    hass.data[DOMAIN]["client"] = aqualink

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    aqualink = hass.data[DOMAIN]["client"]
    await aqualink.close()

    platforms_to_unload = [
        platform for platform in PLATFORMS if platform in hass.data[DOMAIN]
    ]

    del hass.data[DOMAIN]

    return await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)


def refresh_system(
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


class AqualinkEntity(Entity):
    """Abstract class for all Aqualink platforms.

    Entity state is updated via the interval timer within the integration.
    Any entity state change via the iaqualink library triggers an internal
    state refresh which is then propagated to all the entities in the system
    via the refresh_system decorator above to the _update_callback in this
    class.
    """

    _attr_should_poll = False

    def __init__(self, dev: AqualinkDevice) -> None:
        """Initialize the entity."""
        self.dev = dev
        self._attr_unique_id = f"{dev.system.serial}_{dev.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=dev.manufacturer,
            model=dev.model,
            name=dev.label,
            via_device=(DOMAIN, dev.system.serial),
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from the device."""
        return self.dev.system.online in [False, None]

    @property
    def available(self) -> bool:
        """Return whether the device is available or not."""
        return self.dev.system.online is True
