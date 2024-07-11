"""Support for the Hive devices and services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from aiohttp.web_exceptions import HTTPException
from apyhiveapi import Auth, Hive
from apyhiveapi.helper.hive_exceptions import HiveReauthRequired
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORM_LOOKUP, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=2): cv.positive_int,
                },
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Hive configuration setup."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive from a config entry."""

    web_session = aiohttp_client.async_get_clientsession(hass)
    hive_config = dict(entry.data)
    hive = Hive(web_session)

    hive_config["options"] = {}
    hive_config["options"].update(
        {CONF_SCAN_INTERVAL: dict(entry.options).get(CONF_SCAN_INTERVAL, 120)}
    )
    hass.data[DOMAIN][entry.entry_id] = hive

    try:
        devices = await hive.session.startSession(hive_config)
    except HTTPException as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady from error
    except HiveReauthRequired as err:
        raise ConfigEntryAuthFailed from err

    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            ha_type
            for ha_type, hive_type in PLATFORM_LOOKUP.items()
            if devices.get(hive_type)
        ],
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    hive = Auth(entry.data["username"], entry.data["password"])
    await hive.forget_device(
        entry.data["tokens"]["AuthenticationResult"]["AccessToken"],
        entry.data["device_data"][1],
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


def refresh_system[_HiveEntityT: HiveEntity, **_P](
    func: Callable[Concatenate[_HiveEntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_HiveEntityT, _P], Coroutine[Any, Any, None]]:
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self: _HiveEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    def __init__(self, hive: Hive, hive_device: dict[str, Any]) -> None:
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self._attr_name = self.device["haName"]
        self._attr_unique_id = f'{self.device["hiveID"]}-{self.device["hiveType"]}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            model=self.device["deviceData"]["model"],
            manufacturer=self.device["deviceData"]["manufacturer"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
            via_device=(DOMAIN, self.device["parentDevice"]),
        )
        self.attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
