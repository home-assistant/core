"""Support for tracking consumption over given periods of time."""
from datetime import timedelta
import logging

from croniter import croniter
import voluptuous as vol

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import discovery, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CRON_PATTERN,
    CONF_METER,
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_PERIODICALLY_RESETTING,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
    CONF_TARIFFS,
    DATA_TARIFF_SENSORS,
    DATA_UTILITY,
    DOMAIN,
    METER_TYPES,
    SERVICE_RESET,
    SIGNAL_RESET_METER,
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


def max_28_days(config):
    """Check that time period does not include more than 28 days."""
    if config.days >= 28:
        raise vol.Invalid(
            "Unsupported offset of more than 28 days, please use a cron pattern."
        )

    return config


METER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_METER_TYPE): vol.In(METER_TYPES),
            vol.Optional(CONF_METER_OFFSET, default=DEFAULT_OFFSET): vol.All(
                cv.time_period, cv.positive_timedelta, max_28_days
            ),
            vol.Optional(CONF_METER_DELTA_VALUES, default=False): cv.boolean,
            vol.Optional(CONF_METER_NET_CONSUMPTION, default=False): cv.boolean,
            vol.Optional(CONF_METER_PERIODICALLY_RESETTING, default=True): cv.boolean,
            vol.Optional(CONF_TARIFFS, default=[]): vol.All(
                cv.ensure_list, vol.Unique(), [cv.string]
            ),
            vol.Optional(CONF_CRON_PATTERN): validate_cron_pattern,
        },
        period_or_cron,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: METER_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an Utility Meter."""
    hass.data[DATA_UTILITY] = {}

    async def async_reset_meters(service_call):
        """Reset all sensors of a meter."""
        meters = service_call.data["entity_id"]

        for meter in meters:
            _LOGGER.debug("resetting meter %s", meter)
            domain, entity = split_entity_id(meter)
            # backward compatibility up to 2022.07:
            if domain == DOMAIN:
                async_dispatcher_send(
                    hass, SIGNAL_RESET_METER, f"{SELECT_DOMAIN}.{entity}"
                )
            else:
                async_dispatcher_send(hass, SIGNAL_RESET_METER, meter)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET,
        async_reset_meters,
        vol.Schema({ATTR_ENTITY_ID: vol.All(cv.ensure_list, [cv.entity_id])}),
    )

    if DOMAIN not in config:
        return True

    for meter, conf in config[DOMAIN].items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, meter)

        hass.data[DATA_UTILITY][meter] = conf
        hass.data[DATA_UTILITY][meter][DATA_TARIFF_SENSORS] = []

        if not conf[CONF_TARIFFS]:
            # only one entity is required
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    SENSOR_DOMAIN,
                    DOMAIN,
                    {meter: {CONF_METER: meter}},
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
            tariff_confs = {}
            for tariff in conf[CONF_TARIFFS]:
                name = f"{meter} {tariff}"
                tariff_confs[name] = {
                    CONF_METER: meter,
                    CONF_TARIFF: tariff,
                }

            hass.async_create_task(
                discovery.async_load_platform(
                    hass, SENSOR_DOMAIN, DOMAIN, tariff_confs, config
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Utility Meter from a config entry."""
    entity_registry = er.async_get(hass)
    hass.data[DATA_UTILITY][entry.entry_id] = {}
    hass.data[DATA_UTILITY][entry.entry_id][DATA_TARIFF_SENSORS] = []

    try:
        er.async_validate_entity_id(entity_registry, entry.options[CONF_SOURCE_SENSOR])
    except vol.Invalid:
        # The entity is identified by an unknown entity registry ID
        _LOGGER.error(
            "Failed to setup utility_meter for unknown entity %s",
            entry.options[CONF_SOURCE_SENSOR],
        )
        return False

    if not entry.options.get(CONF_TARIFFS):
        # Only a single meter sensor is required
        hass.data[DATA_UTILITY][entry.entry_id][CONF_TARIFF_ENTITY] = None
        await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    else:
        # Create tariff selection + one meter sensor for each tariff
        entity_entry = entity_registry.async_get_or_create(
            Platform.SELECT, DOMAIN, entry.entry_id, suggested_object_id=entry.title
        )
        hass.data[DATA_UTILITY][entry.entry_id][
            CONF_TARIFF_ENTITY
        ] = entity_entry.entity_id
        await hass.config_entries.async_forward_entry_setups(
            entry, (Platform.SELECT, Platform.SENSOR)
        )

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms_to_unload = [Platform.SENSOR]
    if entry.options.get(CONF_TARIFFS):
        platforms_to_unload.append(Platform.SELECT)

    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry,
        platforms_to_unload,
    ):
        hass.data[DATA_UTILITY].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.options}
        new[CONF_METER_PERIODICALLY_RESETTING] = True
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, options=new)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
