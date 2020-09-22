"""Support for ZoneMinder."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .common import (
    ClientAvailabilityResult,
    async_test_client_availability,
    create_client_from_config,
    delete_config_data,
    get_config_data_for_host,
    set_config_data,
)
from .const import (
    CONF_PATH_ZMS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SERVICE_SET_RUN_STATE,
)

_LOGGER = logging.getLogger(__name__)
PLATFORM_DOMAINS = (BINARY_SENSOR_DOMAIN, CAMERA_DOMAIN, SENSOR_DOMAIN)

HOST_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.All(
    cv.deprecated(DOMAIN, invalidation_version="0.118"),
    vol.Schema(
        {DOMAIN: vol.All(cv.ensure_list, [HOST_CONFIG_SCHEMA])},
        extra=vol.ALLOW_EXTRA,
    ),
)

SET_RUN_STATE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ID): cv.string, vol.Required(ATTR_NAME): cv.string}
)


async def async_setup(hass: HomeAssistant, base_config: dict):
    """Set up the ZoneMinder component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Zoneminder config entry."""
    zm_client = create_client_from_config(config_entry.data)

    result = await async_test_client_availability(hass, zm_client)
    if result != ClientAvailabilityResult.AVAILABLE:
        raise ConfigEntryNotReady

    set_config_data(hass, config_entry, zm_client)

    for platform_domain in PLATFORM_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform_domain)
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_RUN_STATE):

        @callback
        def set_active_state(call):
            """Set the ZoneMinder run state to the given state name."""
            zm_id = call.data[ATTR_ID]
            state_name = call.data[ATTR_NAME]
            config_data = get_config_data_for_host(hass, zm_id)
            if not config_data:
                _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
                return

            if not config_data.client.set_active_state(state_name):
                _LOGGER.error(
                    "Unable to change ZoneMinder state. Host: %s, state: %s",
                    zm_id,
                    state_name,
                )

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_RUN_STATE,
            set_active_state,
            schema=SET_RUN_STATE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Zoneminder config entry."""
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(
                config_entry, platform_domain
            )
            for platform_domain in PLATFORM_DOMAINS
        ]
    )

    # If this is the last config to exist, remove the service too.
    if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        hass.services.async_remove(DOMAIN, SERVICE_SET_RUN_STATE)

    delete_config_data(hass, config_entry)

    return True
