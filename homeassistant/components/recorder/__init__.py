"""Support for recording details."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_EXCLUDE, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    convert_include_exclude_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from . import history, statistics, websocket_api
from .const import (
    ATTR_APPLY_FILTER,
    ATTR_KEEP_DAYS,
    ATTR_REPACK,
    CONF_DB_INTEGRITY_CHECK,
    DATA_INSTANCE,
    DOMAIN,
    EXCLUDE_ATTRIBUTES,
    SQLITE_URL_PREFIX,
)
from .core import Recorder
from .tasks import AddRecorderPlatformTask

_LOGGER = logging.getLogger(__name__)


SERVICE_PURGE = "purge"
SERVICE_PURGE_ENTITIES = "purge_entities"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"


SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): cv.positive_int,
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
        vol.Optional(ATTR_APPLY_FILTER, default=False): cv.boolean,
    }
)

ATTR_DOMAINS = "domains"
ATTR_ENTITY_GLOBS = "entity_globs"

SERVICE_PURGE_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
).extend(cv.ENTITY_SERVICE_FIELDS)
SERVICE_ENABLE_SCHEMA = vol.Schema({})
SERVICE_DISABLE_SCHEMA = vol.Schema({})

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_INTEGRITY_CHECK = True
DEFAULT_DB_MAX_RETRIES = 10
DEFAULT_DB_RETRY_WAIT = 3
DEFAULT_COMMIT_INTERVAL = 1

CONF_AUTO_PURGE = "auto_purge"
CONF_AUTO_REPACK = "auto_repack"
CONF_DB_URL = "db_url"
CONF_DB_MAX_RETRIES = "db_max_retries"
CONF_DB_RETRY_WAIT = "db_retry_wait"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"
CONF_PURGE_INTERVAL = "purge_interval"
CONF_EVENT_TYPES = "event_types"
CONF_COMMIT_INTERVAL = "commit_interval"


EXCLUDE_SCHEMA = INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER.extend(
    {vol.Optional(CONF_EVENT_TYPES): vol.All(cv.ensure_list, [cv.string])}
)

FILTER_SCHEMA = INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
    {vol.Optional(CONF_EXCLUDE, default=EXCLUDE_SCHEMA({})): EXCLUDE_SCHEMA}
)


ALLOW_IN_MEMORY_DB = False


def validate_db_url(db_url: str) -> Any:
    """Validate database URL."""
    # Don't allow on-memory sqlite databases
    if (db_url == SQLITE_URL_PREFIX or ":memory:" in db_url) and not ALLOW_IN_MEMORY_DB:
        raise vol.Invalid("In-memory SQLite database is not supported")

    return db_url


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=dict): vol.All(
            cv.deprecated(CONF_PURGE_INTERVAL),
            cv.deprecated(CONF_DB_INTEGRITY_CHECK),
            FILTER_SCHEMA.extend(
                {
                    vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean,
                    vol.Optional(CONF_AUTO_REPACK, default=True): cv.boolean,
                    vol.Optional(CONF_PURGE_KEEP_DAYS, default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Optional(CONF_PURGE_INTERVAL, default=1): cv.positive_int,
                    vol.Optional(CONF_DB_URL): vol.All(cv.string, validate_db_url),
                    vol.Optional(
                        CONF_COMMIT_INTERVAL, default=DEFAULT_COMMIT_INTERVAL
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_MAX_RETRIES, default=DEFAULT_DB_MAX_RETRIES
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_RETRY_WAIT, default=DEFAULT_DB_RETRY_WAIT
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_INTEGRITY_CHECK, default=DEFAULT_DB_INTEGRITY_CHECK
                    ): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def get_instance(hass: HomeAssistant) -> Recorder:
    """Get the recorder instance."""
    instance: Recorder = hass.data[DATA_INSTANCE]
    return instance


@bind_hass
def is_entity_recorded(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if an entity is being recorded.

    Async friendly.
    """
    if DATA_INSTANCE not in hass.data:
        return False
    instance: Recorder = hass.data[DATA_INSTANCE]
    return instance.entity_filter(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    hass.data[DOMAIN] = {}
    exclude_attributes_by_domain: dict[str, set[str]] = {}
    hass.data[EXCLUDE_ATTRIBUTES] = exclude_attributes_by_domain
    conf = config[DOMAIN]
    entity_filter = convert_include_exclude_filter(conf)
    auto_purge = conf[CONF_AUTO_PURGE]
    auto_repack = conf[CONF_AUTO_REPACK]
    keep_days = conf[CONF_PURGE_KEEP_DAYS]
    commit_interval = conf[CONF_COMMIT_INTERVAL]
    db_max_retries = conf[CONF_DB_MAX_RETRIES]
    db_retry_wait = conf[CONF_DB_RETRY_WAIT]
    db_url = conf.get(CONF_DB_URL) or DEFAULT_URL.format(
        hass_config_path=hass.config.path(DEFAULT_DB_FILE)
    )
    exclude = conf[CONF_EXCLUDE]
    exclude_t = exclude.get(CONF_EVENT_TYPES, [])
    if EVENT_STATE_CHANGED in exclude_t:
        _LOGGER.warning(
            "State change events are excluded, recorder will not record state changes."
            "This will become an error in Home Assistant Core 2022.2"
        )
    instance = hass.data[DATA_INSTANCE] = Recorder(
        hass=hass,
        auto_purge=auto_purge,
        auto_repack=auto_repack,
        keep_days=keep_days,
        commit_interval=commit_interval,
        uri=db_url,
        db_max_retries=db_max_retries,
        db_retry_wait=db_retry_wait,
        entity_filter=entity_filter,
        exclude_t=exclude_t,
        exclude_attributes_by_domain=exclude_attributes_by_domain,
    )
    instance.async_initialize()
    instance.async_register()
    instance.start()
    _async_register_services(hass, instance)
    history.async_setup(hass)
    statistics.async_setup(hass)
    websocket_api.async_setup(hass)
    await async_process_integration_platforms(hass, DOMAIN, _process_recorder_platform)

    return await instance.async_db_ready


async def _process_recorder_platform(
    hass: HomeAssistant, domain: str, platform: Any
) -> None:
    """Process a recorder platform."""
    instance: Recorder = hass.data[DATA_INSTANCE]
    instance.queue.put(AddRecorderPlatformTask(domain, platform))


@callback
def _async_register_services(hass: HomeAssistant, instance: Recorder) -> None:
    """Register recorder services."""

    async def async_handle_purge_service(service: ServiceCall) -> None:
        """Handle calls to the purge service."""
        instance.do_adhoc_purge(**service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_PURGE, async_handle_purge_service, schema=SERVICE_PURGE_SCHEMA
    )

    async def async_handle_purge_entities_service(service: ServiceCall) -> None:
        """Handle calls to the purge entities service."""
        entity_ids = await async_extract_entity_ids(hass, service)
        domains = service.data.get(ATTR_DOMAINS, [])
        entity_globs = service.data.get(ATTR_ENTITY_GLOBS, [])

        instance.do_adhoc_purge_entities(entity_ids, domains, entity_globs)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_handle_purge_entities_service,
        schema=SERVICE_PURGE_ENTITIES_SCHEMA,
    )

    async def async_handle_enable_service(service: ServiceCall) -> None:
        instance.set_enable(True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE,
        async_handle_enable_service,
        schema=SERVICE_ENABLE_SCHEMA,
    )

    async def async_handle_disable_service(service: ServiceCall) -> None:
        instance.set_enable(False)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE,
        async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )
