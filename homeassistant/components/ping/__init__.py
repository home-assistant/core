"""The ping component."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

from icmplib import SocketPermissionError, ping as icmp_ping
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    SCAN_INTERVAL as BINARY_SENSOR_DEFAULT_SCAN_INTERVAL,
)
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN, PING_PRIVS

_LOGGER = logging.getLogger(__name__)

PLATFORM_MAPPING = {
    BINARY_SENSOR_DOMAIN: Platform.BINARY_SENSOR,
    DEVICE_TRACKER_DOMAIN: Platform.DEVICE_TRACKER,
}

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PING_COUNT, default=DEFAULT_PING_COUNT): vol.Range(
            min=1, max=100
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=BINARY_SENSOR_DEFAULT_SCAN_INTERVAL
        ): vol.All(cv.time_period, cv.positive_timedelta),
    }
)
DEVICE_TRACKER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)
COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(BINARY_SENSOR_DOMAIN): BINARY_SENSOR_SCHEMA,
        vol.Optional(DEVICE_TRACKER_DOMAIN): DEVICE_TRACKER_SCHEMA,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.All(
            cv.ensure_list,
            [COMBINED_SCHEMA],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ping integration."""

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload Command Line."""
        reload_config = await async_integration_yaml_config(hass, DOMAIN)
        reset_platforms = async_get_platforms(hass, DOMAIN)
        for reset_platform in reset_platforms:
            _LOGGER.debug("Reload resetting platform: %s", reset_platform.domain)
            await reset_platform.async_reset()
        if not reload_config:
            return
        await async_load_platforms(hass, reload_config.get(DOMAIN, []), reload_config)

    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    hass.data[DOMAIN] = {
        PING_PRIVS: await hass.async_add_executor_job(_can_use_icmp_lib_with_privilege),
    }

    await async_load_platforms(hass, config.get(DOMAIN, []), config)

    return True


async def async_load_platforms(
    hass: HomeAssistant,
    ping_config: list[dict[str, dict[str, Any]]],
    config: ConfigType,
) -> None:
    """Load platforms from yaml."""
    if not ping_config:
        return

    _LOGGER.debug("Full config loaded: %s", ping_config)

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    platforms: list[Platform] = []
    reload_configs: list[tuple] = []
    for platform_config in ping_config:
        for platform, _config in platform_config.items():
            if (mapped_platform := PLATFORM_MAPPING[platform]) not in platforms:
                platforms.append(mapped_platform)
            _LOGGER.debug(
                "Loading config %s for platform %s",
                platform_config,
                PLATFORM_MAPPING[platform],
            )
            reload_configs.append((PLATFORM_MAPPING[platform], _config))
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    PLATFORM_MAPPING[platform],
                    DOMAIN,
                    _config,
                    config,
                )
            )

    if load_coroutines:
        _LOGGER.debug("Loading platforms: %s", platforms)
        await asyncio.gather(*load_coroutines)


def _can_use_icmp_lib_with_privilege() -> None | bool:
    """Verify we can create a raw socket."""
    try:
        icmp_ping("127.0.0.1", count=0, timeout=0, privileged=True)
    except SocketPermissionError:
        try:
            icmp_ping("127.0.0.1", count=0, timeout=0, privileged=False)
        except SocketPermissionError:
            _LOGGER.debug(
                "Cannot use icmplib because privileges are insufficient to create the"
                " socket"
            )
            return None

        _LOGGER.debug("Using icmplib in privileged=False mode")
        return False

    _LOGGER.debug("Using icmplib in privileged=True mode")
    return True
