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
from homeassistant.util import Throttle

from .const import (
    CONF_LOCATION,
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

LOGGER = logging.getLogger(__name__)

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
    """Set up the pi_hole integration."""

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

    def get_pi_hole_from_name(name):
        pi_hole = hass.data[DOMAIN].get(name)
        if pi_hole is None:
            LOGGER.error("Unknown Pi-hole name %s", name)
            return None
        if not pi_hole.api.api_token:
            LOGGER.error(
                "Pi-hole %s must have an api_key provided in configuration to be enabled",
                name,
            )
            return None
        return pi_hole

    async def disable_service_handler(call):
        """Handle the service call to disable a single Pi-Hole or all configured Pi-Holes."""
        duration = call.data[SERVICE_DISABLE_ATTR_DURATION].total_seconds()
        name = call.data.get(SERVICE_DISABLE_ATTR_NAME)

        async def do_disable(name):
            """Disable the named Pi-Hole."""
            pi_hole = get_pi_hole_from_name(name)
            if pi_hole is None:
                return

            LOGGER.debug(
                "Disabling Pi-hole '%s' (%s) for %d seconds",
                name,
                pi_hole.api.host,
                duration,
            )
            await pi_hole.api.disable(duration)

        if name is not None:
            await do_disable(name)
        else:
            for name in hass.data[DOMAIN]:
                await do_disable(name)

    async def enable_service_handler(call):
        """Handle the service call to enable a single Pi-Hole or all configured Pi-Holes."""

        name = call.data.get(SERVICE_ENABLE_ATTR_NAME)

        async def do_enable(name):
            """Enable the named Pi-Hole."""
            pi_hole = get_pi_hole_from_name(name)
            if pi_hole is None:
                return

            LOGGER.debug("Enabling Pi-hole '%s' (%s)", name, pi_hole.api.host)
            await pi_hole.api.enable()

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

    LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    try:
        session = async_get_clientsession(hass, verify_tls)
        pi_hole = PiHoleData(
            Hole(
                host,
                hass.loop,
                session,
                location=location,
                tls=use_tls,
                api_token=api_key,
            ),
            name,
        )
        await pi_hole.async_update()
        hass.data[DOMAIN][name] = pi_hole
    except HoleError as ex:
        LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload pi-hole entry."""
    hass.data[DOMAIN].pop(entry.data[CONF_NAME])
    return await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)


class PiHoleData:
    """Get the latest data and update the states."""

    def __init__(self, api, name):
        """Initialize the data object."""
        self.api = api
        self.name = name
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Pi-hole."""

        try:
            await self.api.get_data()
            self.available = True
        except HoleError:
            LOGGER.error("Unable to fetch data from Pi-hole")
            self.available = False
