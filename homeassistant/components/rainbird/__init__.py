"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import asyncio
import logging

from pyrainbird.async_client import (
    AsyncRainbirdClient,
    AsyncRainbirdController,
    RainbirdApiException,
)
import voluptuous as vol

from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TRIGGER_TIME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ZONES,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
)
from .coordinator import RainbirdUpdateCoordinator

PLATFORMS = [Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rainbird"

TRIGGER_TIME_SCHEMA = vol.All(
    cv.time_period, cv.positive_timedelta, lambda td: (td.total_seconds() // 60)
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
    }
)
CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
        vol.Optional(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CONTROLLER_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rain Bird component."""
    return all(
        await asyncio.gather(
            *[
                _setup_controller(hass, controller_config, config)
                for controller_config in config[DOMAIN]
            ]
        )
    )


async def _setup_controller(hass, controller_config, config):
    """Set up a controller."""
    server = controller_config[CONF_HOST]
    password = controller_config[CONF_PASSWORD]
    client = AsyncRainbirdClient(async_get_clientsession(hass), server, password)
    controller = AsyncRainbirdController(client)
    try:
        await controller.get_serial_number()
    except RainbirdApiException as exc:
        _LOGGER.error("Unable to setup controller: %s", exc)
        return False

    rain_coordinator = RainbirdUpdateCoordinator(hass, controller.get_rain_sensor_state)
    delay_coordinator = RainbirdUpdateCoordinator(hass, controller.get_rain_delay)

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                platform,
                DOMAIN,
                {
                    RAINBIRD_CONTROLLER: controller,
                    SENSOR_TYPE_RAINSENSOR: rain_coordinator,
                    SENSOR_TYPE_RAINDELAY: delay_coordinator,
                    **controller_config,
                },
                config,
            )
        )
    return True
