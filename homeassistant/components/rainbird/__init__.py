"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import asyncio
import logging

import async_timeout
from pyrainbird.async_client import (
    AsyncRainbirdClient,
    AsyncRainbirdController,
    RainbirdApiException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TRIGGER_TIME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DURATION,
    CONF_ZONES,
    DEVICE_INFO,
    MANUFACTURER,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SERIAL_NUMBER,
    TIMEOUT_SECONDS,
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

SERVICE_SET_RAIN_DELAY = "set_rain_delay"
SERVICE_SCHEMA_RAIN_DELAY = vol.Schema(
    {
        vol.Required(ATTR_DURATION): cv.positive_float,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rain Bird component."""
    if DOMAIN not in config:
        return True

    for controller_config in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=controller_config,
            )
        )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.3.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the config entry for Rain Bird."""
    hass.data.setdefault(DOMAIN, {})

    controller = AsyncRainbirdController(
        AsyncRainbirdClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PASSWORD],
        )
    )

    try:
        async with async_timeout.timeout(TIMEOUT_SECONDS):
            serial_number = await controller.get_serial_number()
    except (RainbirdApiException, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady(f"Error talking to controller: {str(err)}") from err

    device_info = DeviceInfo(
        default_name=MANUFACTURER,
        identifiers={(DOMAIN, serial_number)},
        manufacturer=MANUFACTURER,
    )
    rain_coordinator = RainbirdUpdateCoordinator(
        hass, "Rain", controller.get_rain_sensor_state
    )
    delay_coordinator = RainbirdUpdateCoordinator(
        hass, "Rain delay", controller.get_rain_delay
    )

    hass.data[DOMAIN][entry.entry_id] = {
        SERIAL_NUMBER: serial_number,
        DEVICE_INFO: device_info,
        RAINBIRD_CONTROLLER: controller,
        SENSOR_TYPE_RAINSENSOR: rain_coordinator,
        SENSOR_TYPE_RAINDELAY: delay_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def set_rain_delay(service: ServiceCall) -> None:
        await controller.set_rain_delay(service.data[ATTR_DURATION])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_RAIN_DELAY,
        set_rain_delay,
        schema=SERVICE_SCHEMA_RAIN_DELAY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    if unload_ok and not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SET_RAIN_DELAY)

    return unload_ok
