"""Support for tracking consumption over given periods of time."""

from datetime import datetime, timedelta
import logging

from cronsim import CronSim, CronSimError
import voluptuous as vol

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CRON_PATTERN,
    CONF_METER,
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_PERIODICALLY_RESETTING,
    CONF_METER_TYPE,
    CONF_SENSOR_ALWAYS_AVAILABLE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
    CONF_TARIFFS,
    DATA_TARIFF_SENSORS,
    DATA_UTILITY,
    DOMAIN,
    METER_TYPES,
    MeterInformation,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

DEFAULT_OFFSET = timedelta(hours=0)


def validate_cron_pattern(pattern: str) -> str:
    """Check that the pattern is well-formed."""
    try:
        CronSim(pattern, datetime(2020, 1, 1))  # any date will do
    except CronSimError as err:
        _LOGGER.error("Invalid cron pattern %s: %s", pattern, err)
        raise vol.Invalid("Invalid pattern") from err
    return pattern


def period_or_cron(config: ConfigType) -> ConfigType:
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


def max_28_days(config: timedelta) -> timedelta:
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
            vol.Optional(CONF_SENSOR_ALWAYS_AVAILABLE, default=False): cv.boolean,
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

    async_setup_services(hass)

    if DOMAIN not in config:
        return True

    domain_config: ConfigType = config[DOMAIN]
    for meter, conf in domain_config.items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, meter)

        meter_info: MeterInformation = {**conf, DATA_TARIFF_SENSORS: []}
        hass.data[DATA_UTILITY][meter] = meter_info

        if not conf[CONF_TARIFFS]:
            # only one entity is required
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    SENSOR_DOMAIN,
                    DOMAIN,
                    {meter: {CONF_METER: meter}},
                    config,
                ),
                eager_start=True,
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
                ),
                eager_start=True,
            )

            meter_info[CONF_TARIFF_ENTITY] = f"{SELECT_DOMAIN}.{meter}"

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
                ),
                eager_start=True,
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Utility Meter from a config entry."""

    entity_registry = er.async_get(hass)

    entry_meter_info: MeterInformation = {
        "source": entry.options[CONF_SOURCE_SENSOR],
        DATA_TARIFF_SENSORS: [],
    }
    hass.data[DATA_UTILITY][entry.entry_id] = entry_meter_info

    try:
        er.async_validate_entity_id(entity_registry, entry.options[CONF_SOURCE_SENSOR])
    except vol.Invalid:
        # The entity is identified by an unknown entity registry ID
        _LOGGER.error(
            "Failed to setup utility_meter for unknown entity %s",
            entry.options[CONF_SOURCE_SENSOR],
        )
        return False

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SOURCE_SENSOR: source_entity_id},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            add_helper_config_entry_to_device=False,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_SOURCE_SENSOR]
            ),
            source_entity_id_or_uuid=entry.options[CONF_SOURCE_SENSOR],
        )
    )

    if not entry.options.get(CONF_TARIFFS):
        # Only a single meter sensor is required
        entry_meter_info[CONF_TARIFF_ENTITY] = None
        await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    else:
        # Create tariff selection + one meter sensor for each tariff
        entity_entry = entity_registry.async_get_or_create(
            Platform.SELECT, DOMAIN, entry.entry_id, object_id_base=entry.title
        )
        entry_meter_info[CONF_TARIFF_ENTITY] = entity_entry.entity_id
        await hass.config_entries.async_forward_entry_setups(
            entry, (Platform.SELECT, Platform.SENSOR)
        )

    return True


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
    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new = {**config_entry.options}
        new[CONF_METER_PERIODICALLY_RESETTING] = True
        hass.config_entries.async_update_entry(config_entry, options=new, version=2)

    if config_entry.version == 2:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            # Remove the utility_meter config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, options[CONF_SOURCE_SENSOR]
            ):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
