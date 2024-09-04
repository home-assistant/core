"""The generic_hygrostat component."""

import voluptuous as vol

from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.typing import ConfigType

DOMAIN = "generic_hygrostat"

CONF_HUMIDIFIER = "humidifier"
CONF_SENSOR = "target_sensor"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_TARGET_HUMIDITY = "target_humidity"
CONF_DEVICE_CLASS = "device_class"
CONF_MIN_DUR = "min_cycle_duration"
CONF_DRY_TOLERANCE = "dry_tolerance"
CONF_WET_TOLERANCE = "wet_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_STATE = "initial_state"
CONF_AWAY_HUMIDITY = "away_humidity"
CONF_AWAY_FIXED = "away_fixed"
CONF_STALE_DURATION = "sensor_stale_duration"


DEFAULT_TOLERANCE = 3
DEFAULT_NAME = "Generic Hygrostat"

HYGROSTAT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HUMIDIFIER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_DEVICE_CLASS): vol.In(
            [HumidifierDeviceClass.HUMIDIFIER, HumidifierDeviceClass.DEHUMIDIFIER]
        ),
        vol.Optional(CONF_MAX_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_MIN_DUR): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_MIN_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DRY_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_WET_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_TARGET_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_INITIAL_STATE): cv.boolean,
        vol.Optional(CONF_AWAY_HUMIDITY): vol.Coerce(int),
        vol.Optional(CONF_AWAY_FIXED): cv.boolean,
        vol.Optional(CONF_STALE_DURATION): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [HYGROSTAT_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Generic Hygrostat component."""
    if DOMAIN not in config:
        return True

    for hygrostat_conf in config[DOMAIN]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.HUMIDIFIER, DOMAIN, hygrostat_conf, config
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        entry.options[CONF_HUMIDIFIER],
    )

    await hass.config_entries.async_forward_entry_setups(entry, (Platform.HUMIDIFIER,))
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (Platform.HUMIDIFIER,)
    )
