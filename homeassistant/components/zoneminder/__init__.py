"""Support for ZoneMinder."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
import homeassistant.config_entries as config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_SOURCE,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from . import const
from .common import (
    ClientAvailabilityResult,
    async_test_client_availability,
    create_client_from_config,
    del_client_from_data,
    get_client_from_data,
    is_client_in_data,
    set_client_to_data,
    set_platform_configs,
)

_LOGGER = logging.getLogger(__name__)
PLATFORM_DOMAINS = tuple(
    [BINARY_SENSOR_DOMAIN, CAMERA_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]
)

HOST_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=const.DEFAULT_PATH): cv.string,
        vol.Optional(const.CONF_PATH_ZMS, default=const.DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=const.DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=const.DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.All(
    cv.deprecated(const.DOMAIN, invalidation_version="0.118"),
    vol.Schema(
        {const.DOMAIN: vol.All(cv.ensure_list, [HOST_CONFIG_SCHEMA])},
        extra=vol.ALLOW_EXTRA,
    ),
)

SET_RUN_STATE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ID): cv.string, vol.Required(ATTR_NAME): cv.string}
)


async def async_setup(hass: HomeAssistant, base_config: dict):
    """Set up the ZoneMinder component."""

    # Collect the platform specific configs. It's necessary to collect these configs
    # here instead of the platform's setup_platform function because the invocation order
    # of setup_platform and async_setup_entry is not consistent.
    set_platform_configs(
        hass,
        SENSOR_DOMAIN,
        [
            platform_config
            for platform_config in base_config.get(SENSOR_DOMAIN, [])
            if platform_config[CONF_PLATFORM] == const.DOMAIN
        ],
    )
    set_platform_configs(
        hass,
        SWITCH_DOMAIN,
        [
            platform_config
            for platform_config in base_config.get(SWITCH_DOMAIN, [])
            if platform_config[CONF_PLATFORM] == const.DOMAIN
        ],
    )

    config = base_config.get(const.DOMAIN)

    if not config:
        return True

    for config_item in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                const.DOMAIN,
                context={CONF_SOURCE: config_entries.SOURCE_IMPORT},
                data=config_item,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Zoneminder config entry."""
    zm_client = create_client_from_config(config_entry.data)

    result = await async_test_client_availability(hass, zm_client)
    if result != ClientAvailabilityResult.AVAILABLE:
        raise ConfigEntryNotReady

    set_client_to_data(hass, config_entry.unique_id, zm_client)

    for platform_domain in PLATFORM_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform_domain)
        )

    if not hass.services.has_service(const.DOMAIN, const.SERVICE_SET_RUN_STATE):

        @callback
        def set_active_state(call):
            """Set the ZoneMinder run state to the given state name."""
            zm_id = call.data[ATTR_ID]
            state_name = call.data[ATTR_NAME]
            if not is_client_in_data(hass, zm_id):
                _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
                return

            if not get_client_from_data(hass, zm_id).set_active_state(state_name):
                _LOGGER.error(
                    "Unable to change ZoneMinder state. Host: %s, state: %s",
                    zm_id,
                    state_name,
                )

        hass.services.async_register(
            const.DOMAIN,
            const.SERVICE_SET_RUN_STATE,
            set_active_state,
            schema=SET_RUN_STATE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Zoneminder config entry."""
    for platform_domain in PLATFORM_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(
                config_entry, platform_domain
            )
        )

    # If this is the last config to exist, remove the service too.
    if len(hass.config_entries.async_entries(const.DOMAIN)) <= 1:
        hass.services.async_remove(const.DOMAIN, const.SERVICE_SET_RUN_STATE)

    del_client_from_data(hass, config_entry.unique_id)

    return True
