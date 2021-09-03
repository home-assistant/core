"""Support for tracking consumption over given periods of time."""
from datetime import timedelta
import logging

from croniter import croniter
import voluptuous as vol

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CRON_PATTERN,
    CONF_METER,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
    CONF_TARIFFS,
    DATA_UTILITY,
    DOMAIN,
    METER_TYPES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_OFFSET = timedelta(hours=0)


def validate_cron_pattern(pattern):
    """Check that the pattern is well-formed."""
    if croniter.is_valid(pattern):
        return pattern
    raise vol.Invalid("Invalid pattern")


def period_or_cron(config):
    """Check that if cron pattern is used, then meter type and offsite must be removed."""
    if CONF_CRON_PATTERN in config and CONF_METER_TYPE in config:
        raise vol.Invalid(f"Use <{CONF_CRON_PATTERN}> or <{CONF_METER_TYPE}>")
    if (
        CONF_CRON_PATTERN in config
        and CONF_METER_OFFSET in config
        and config[CONF_METER_OFFSET] != DEFAULT_OFFSET
    ):
        raise vol.Invalid(
            f"When <{CONF_CRON_PATTERN}> is used <{CONF_METER_OFFSET}> has no meaning"
        )
    return config


METER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_METER_TYPE): vol.In(METER_TYPES),
            vol.Optional(CONF_METER_OFFSET, default=DEFAULT_OFFSET): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(CONF_METER_NET_CONSUMPTION, default=False): cv.boolean,
            vol.Optional(CONF_TARIFFS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_CRON_PATTERN): validate_cron_pattern,
        },
        period_or_cron,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: METER_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up an Utility Meter."""
    hass.data[DATA_UTILITY] = {}

    for meter, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, meter)

        hass.data[DATA_UTILITY][meter] = conf

        if not conf[CONF_TARIFFS]:
            # only one entity is required
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    SENSOR_DOMAIN,
                    DOMAIN,
                    [{CONF_METER: meter, CONF_NAME: conf.get(CONF_NAME, meter)}],
                    config,
                )
            )
        else:
            # create tariff selection
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    SELECT_DOMAIN,
                    DOMAIN,
                    {CONF_METER: meter, CONF_TARIFFS: conf[CONF_TARIFFS]},
                    config,
                )
            )

            hass.data[DATA_UTILITY][meter][CONF_TARIFF_ENTITY] = "{}.{}".format(
                SELECT_DOMAIN, meter
            )

            # add one meter for each tariff
            tariff_confs = []
            for tariff in conf[CONF_TARIFFS]:
                tariff_confs.append(
                    {
                        CONF_METER: meter,
                        CONF_NAME: f"{meter} {tariff}",
                        CONF_TARIFF: tariff,
                    }
                )
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, SENSOR_DOMAIN, DOMAIN, tariff_confs, config
                )
            )

    return True
