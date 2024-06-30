"""The history_stats component."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_STATE,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DURATION,
    CONF_END,
    CONF_PERIOD_KEYS,
    CONF_START,
    CONF_TYPE_KEYS,
    CONF_TYPE_TIME,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


def exactly_two_period_keys[_T: dict[str, Any]](conf: _T) -> _T:
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    if sum(param in conf for param in CONF_PERIOD_KEYS) != 2:
        raise vol.Invalid(
            "You must provide exactly 2 of the following: start, end, duration"
        )
    return conf


SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_STATE): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_START): cv.template,
            vol.Optional(CONF_END): cv.template,
            vol.Optional(CONF_DURATION): cv.time_period,
            vol.Optional(CONF_TYPE, default=CONF_TYPE_TIME): vol.In(CONF_TYPE_KEYS),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
    exactly_two_period_keys,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.All(
            cv.ensure_list,
            [SENSOR_SCHEMA],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up history_stats from yaml config."""
    if DOMAIN in config:
        await _process_config(hass, config)

        async def _reload_config(call: Event | ServiceCall) -> None:
            """Reload top-level + platforms."""
            try:
                unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
            except HomeAssistantError as err:
                _LOGGER.error(err)
                return

            integration = await async_get_integration(hass, DOMAIN)
            conf = await conf_util.async_process_component_and_handle_errors(
                hass, unprocessed_conf, integration
            )

            if conf is None:
                return

            await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

            if DOMAIN in conf:
                await _process_config(hass, conf)

            hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    return True


async def _process_config(hass: HomeAssistant, config: ConfigType) -> None:
    """Process config."""

    history_stats_config: list[dict[str, Any]] = config.get(DOMAIN, {})

    if not history_stats_config:
        return

    _LOGGER.debug("Full config loaded: %s", history_stats_config)

    load_coroutines: list[Coroutine[Any, Any, None]] = [
        discovery.async_load_platform(
            hass,
            Platform.SENSOR,
            DOMAIN,
            _config,
            config,
        )
        for _config in history_stats_config
    ]

    if load_coroutines:
        await asyncio.gather(*load_coroutines)

    return
