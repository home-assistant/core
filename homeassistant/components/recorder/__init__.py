"""Support for recording details."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_EXCLUDE,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,  # noqa: F401
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,  # noqa: F401
    EVENT_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    convert_include_exclude_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.recorder import DATA_INSTANCE
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.event_type import EventType

from . import entity_registry, websocket_api
from .const import (  # noqa: F401
    CONF_DB_INTEGRITY_CHECK,
    DOMAIN,
    INTEGRATION_PLATFORM_COMPILE_STATISTICS,
    INTEGRATION_PLATFORM_METHODS,
    SQLITE_URL_PREFIX,
    SupportedDialect,
)
from .core import Recorder
from .services import async_register_services
from .tasks import AddRecorderPlatformTask
from .util import get_instance

_LOGGER = logging.getLogger(__name__)


DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_INTEGRITY_CHECK = True
DEFAULT_DB_MAX_RETRIES = 10
DEFAULT_DB_RETRY_WAIT = 3
DEFAULT_COMMIT_INTERVAL = 5

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
    if (
        db_url == SQLITE_URL_PREFIX
        or (db_url.startswith(SQLITE_URL_PREFIX) and ":memory:" in db_url)
    ) and not ALLOW_IN_MEMORY_DB:
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


@bind_hass
def is_entity_recorded(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if an entity is being recorded.

    Async friendly.
    """
    instance = get_instance(hass)
    return instance.entity_filter is None or instance.entity_filter(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    conf = config[DOMAIN]
    _filter = convert_include_exclude_filter(conf)
    entity_filter = None if _filter.empty_filter else _filter.get_filter()
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
    exclude_event_types: set[EventType[Any] | str] = set(
        exclude.get(CONF_EVENT_TYPES, [])
    )
    if EVENT_STATE_CHANGED in exclude_event_types:
        _LOGGER.error("State change events cannot be excluded, use a filter instead")
        exclude_event_types.remove(EVENT_STATE_CHANGED)
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
        exclude_event_types=exclude_event_types,
    )
    get_instance.cache_clear()
    instance.async_initialize()
    instance.async_register()
    instance.start()
    async_register_services(hass, instance)
    websocket_api.async_setup(hass)
    entity_registry.async_setup(hass)

    await _async_setup_integration_platform(hass, instance)

    return await instance.async_db_ready


async def _async_setup_integration_platform(
    hass: HomeAssistant, instance: Recorder
) -> None:
    """Set up a recorder integration platform."""

    @callback
    def _process_recorder_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process a recorder platform."""
        # If the platform has a compile_statistics method, we need to
        # add it to the recorder queue to be processed.
        if any(hasattr(platform, _attr) for _attr in INTEGRATION_PLATFORM_METHODS):
            instance.queue_task(AddRecorderPlatformTask(domain, platform))

    await async_process_integration_platforms(hass, DOMAIN, _process_recorder_platform)
