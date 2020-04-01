"""The pi_hole component."""
import logging

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util import Throttle

from .const import (
    CONF_LOCATION,
    CONF_SLUG,
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


def ensure_unique_names_and_slugs(config):
    """Ensure that each configuration dict contains a unique `name` value."""
    names = {}
    slugs = {}
    for conf in config:
        if conf[CONF_NAME] not in names and conf[CONF_SLUG] not in slugs:
            names[conf[CONF_NAME]] = conf[CONF_HOST]
            slugs[conf[CONF_SLUG]] = conf[CONF_HOST]
        else:
            raise vol.Invalid(
                "Duplicate name '{}' (or slug '{}') for '{}' (already in use by '{}'). Each configured Pi-hole must have a unique name.".format(
                    conf[CONF_NAME],
                    conf[CONF_SLUG],
                    conf[CONF_HOST],
                    names.get(conf[CONF_NAME], slugs[conf[CONF_SLUG]]),
                )
            )
    return config


def coerce_slug(config):
    """Coerce the name of the Pi-Hole into a slug."""
    config[CONF_SLUG] = cv.slugify(config[CONF_NAME])
    return config


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
        coerce_slug,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(cv.ensure_list, [PI_HOLE_SCHEMA], ensure_unique_names_and_slugs)
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the pi_hole integration."""

    def get_data():
        """Retrieve component data."""
        return hass.data[DOMAIN]

    def ensure_api_token(call_data):
        """Ensure the Pi-Hole to be enabled/disabled has a api_token configured."""
        data = get_data()
        if SERVICE_DISABLE_ATTR_NAME not in call_data:
            for slug in data:
                call_data[SERVICE_DISABLE_ATTR_NAME] = data[slug].name
                ensure_api_token(call_data)

            call_data[SERVICE_DISABLE_ATTR_NAME] = None
        else:
            slug = cv.slugify(call_data[SERVICE_DISABLE_ATTR_NAME])

            if (data[slug]).api.api_token is None:
                raise vol.Invalid(
                    "Pi-hole '{}' must have an api_key provided in configuration to be enabled.".format(
                        pi_hole.name
                    )
                )

        return call_data

    service_disable_schema = vol.Schema(
        vol.All(
            {
                vol.Required(SERVICE_DISABLE_ATTR_DURATION): vol.All(
                    cv.time_period_str, cv.positive_timedelta
                ),
                vol.Optional(SERVICE_DISABLE_ATTR_NAME): vol.In(
                    [conf[CONF_NAME] for conf in config[DOMAIN]], msg="Unknown Pi-Hole",
                ),
            },
            ensure_api_token,
        )
    )

    service_enable_schema = vol.Schema(
        {
            vol.Optional(SERVICE_ENABLE_ATTR_NAME): vol.In(
                [conf[CONF_NAME] for conf in config[DOMAIN]], msg="Unknown Pi-Hole"
            )
        }
    )

    hass.data[DOMAIN] = {}

    for conf in config[DOMAIN]:
        name = conf[CONF_NAME]
        slug = conf[CONF_SLUG]
        host = conf[CONF_HOST]
        use_tls = conf[CONF_SSL]
        verify_tls = conf[CONF_VERIFY_SSL]
        location = conf[CONF_LOCATION]
        api_key = conf.get(CONF_API_KEY)

        LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

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

        hass.data[DOMAIN][slug] = pi_hole

    async def disable_service_handler(call):
        """Handle the service call to disable a single Pi-Hole or all configured Pi-Holes."""
        duration = call.data[SERVICE_DISABLE_ATTR_DURATION].total_seconds()
        name = call.data.get(SERVICE_DISABLE_ATTR_NAME)

        async def do_disable(name):
            """Disable the named Pi-Hole."""
            slug = cv.slugify(name)
            pi_hole = hass.data[DOMAIN][slug]

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
            for pi_hole in hass.data[DOMAIN].values():
                await do_disable(pi_hole.name)

    async def enable_service_handler(call):
        """Handle the service call to enable a single Pi-Hole or all configured Pi-Holes."""

        name = call.data.get(SERVICE_ENABLE_ATTR_NAME)

        async def do_enable(name):
            """Enable the named Pi-Hole."""
            slug = cv.slugify(name)
            pi_hole = hass.data[DOMAIN][slug]

            LOGGER.debug("Enabling Pi-hole '%s' (%s)", name, pi_hole.api.host)
            await pi_hole.api.enable()

        if name is not None:
            await do_enable(name)
        else:
            for pi_hole in hass.data[DOMAIN].values():
                await do_enable(pi_hole.name)

    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE, disable_service_handler, schema=service_disable_schema
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE, enable_service_handler, schema=service_enable_schema
    )

    hass.async_create_task(async_load_platform(hass, SENSOR_DOMAIN, DOMAIN, {}, config))

    return True


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
