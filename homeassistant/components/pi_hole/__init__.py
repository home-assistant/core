"""The pi_hole component."""
import logging

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LOCATION,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    SERVICE_DISABLE,
    SERVICE_DISABLE_ATTR_DURATION,
    SERVICE_DISABLE_ATTR_NAME,
    SERVICE_ENABLE,
    SERVICE_ENABLE_ATTR_NAME,
)

_LOGGER = logging.getLogger(__name__)

PI_HOLE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_API_KEY): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [PI_HOLE_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Pi_hole integration."""

    service_disable_schema = vol.Schema(
        vol.All(
            {
                vol.Required(SERVICE_DISABLE_ATTR_DURATION): vol.All(
                    cv.time_period_str, cv.positive_timedelta
                ),
                vol.Optional(SERVICE_DISABLE_ATTR_NAME): str,
            },
        )
    )

    service_enable_schema = vol.Schema({vol.Optional(SERVICE_ENABLE_ATTR_NAME): str})

    hass.data[DOMAIN] = {}

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    def get_api_from_name(name):
        """Get Pi-hole API object from user configured name."""
        hole_data = hass.data[DOMAIN].get(name)
        if hole_data is None:
            _LOGGER.error("Unknown Pi-hole name %s", name)
            return None
        api = hole_data[DATA_KEY_API]
        if not api.api_token:
            _LOGGER.error(
                "Pi-hole %s must have an api_key provided in configuration to be enabled",
                name,
            )
            return None
        return api

    async def disable_service_handler(call):
        """Handle the service call to disable a single Pi-hole or all configured Pi-holes."""
        duration = call.data[SERVICE_DISABLE_ATTR_DURATION].total_seconds()
        name = call.data.get(SERVICE_DISABLE_ATTR_NAME)

        async def do_disable(name):
            """Disable the named Pi-hole."""
            api = get_api_from_name(name)
            if api is None:
                return

            _LOGGER.debug(
                "Disabling Pi-hole '%s' (%s) for %d seconds", name, api.host, duration,
            )
            await api.disable(duration)

        if name is not None:
            await do_disable(name)
        else:
            for name in hass.data[DOMAIN]:
                await do_disable(name)

    async def enable_service_handler(call):
        """Handle the service call to enable a single Pi-hole or all configured Pi-holes."""

        name = call.data.get(SERVICE_ENABLE_ATTR_NAME)

        async def do_enable(name):
            """Enable the named Pi-hole."""
            api = get_api_from_name(name)
            if api is None:
                return

            _LOGGER.debug("Enabling Pi-hole '%s' (%s)", name, api.host)
            await api.enable()

        if name is not None:
            await do_enable(name)
        else:
            for name in hass.data[DOMAIN]:
                await do_enable(name)

    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE, disable_service_handler, schema=service_disable_schema
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE, enable_service_handler, schema=service_enable_schema
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up Pi-hole entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    use_tls = entry.data[CONF_SSL]
    verify_tls = entry.data[CONF_VERIFY_SSL]
    location = entry.data[CONF_LOCATION]
    api_key = entry.data.get(CONF_API_KEY)

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    try:
        session = async_get_clientsession(hass, verify_tls)
        api = Hole(
            host, hass.loop, session, location=location, tls=use_tls, api_token=api_key,
        )
        await api.get_data()
    except HoleError as ex:
        _LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            await api.get_data()
        except HoleError as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    hass.data[DOMAIN][name] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload pi-hole entry."""
    hass.data[DOMAIN].pop(entry.data[CONF_NAME])
    return await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
