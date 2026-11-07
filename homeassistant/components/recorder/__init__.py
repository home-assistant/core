"""Support for recording details."""

import logging
from typing import Any

import probatio
from sqlalchemy import URL, make_url
from sqlalchemy.exc import ArgumentError

from homeassistant.const import CONF_EXCLUDE, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    convert_include_exclude_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.recorder import DATA_INSTANCE, get_instance
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.event_type import EventType

# Pre-import backup to avoid it being imported
# later when the import executor is busy and delaying
# startup
from . import (
    backup,  # noqa: F401
    entity_options,
    entity_registry,
    settings as recorder_settings,
    websocket_api,
)
from .const import (
    CONF_AUTO_PURGE,
    CONF_AUTO_REPACK,
    CONF_COMMIT_INTERVAL,
    CONF_DB_INTEGRITY_CHECK,
    CONF_DB_MAX_RETRIES,
    CONF_DB_RETRY_WAIT,
    CONF_PURGE_KEEP_DAYS,
    DOMAIN,
    INTEGRATION_PLATFORM_METHODS,
    SupportedDialect,
)
from .core import Recorder
from .entity_options import is_entity_recorded
from .services import async_setup_services
from .settings import DEFAULT_SETTINGS, SETTINGS_SCHEMA_DICT, async_get_settings
from .tasks import AddRecorderPlatformTask
from .util import get_engine_db_url, is_file_sqlite_url

_LOGGER = logging.getLogger(__name__)


DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_INTEGRITY_CHECK = True

CONF_DB_URL = "db_url"
CONF_PURGE_INTERVAL = "purge_interval"
CONF_EVENT_TYPES = "event_types"


EXCLUDE_SCHEMA = INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER.extend(
    {
        probatio.Optional(CONF_EVENT_TYPES): probatio.All(
            probatio.EnsureList(), [cv.string]
        )
    }
)

FILTER_SCHEMA = INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
    {probatio.Optional(CONF_EXCLUDE, default=EXCLUDE_SCHEMA({})): EXCLUDE_SCHEMA}
)


ALLOW_IN_MEMORY_DB = False

__all__ = [
    "CONF_AUTO_PURGE",
    "CONF_AUTO_REPACK",
    "CONF_COMMIT_INTERVAL",
    "CONF_DB_MAX_RETRIES",
    "CONF_DB_RETRY_WAIT",
    "CONF_DB_URL",
    "CONF_PURGE_KEEP_DAYS",
    "DEFAULT_DB_FILE",
    "DOMAIN",
    "Recorder",
    "SupportedDialect",
    "get_engine_db_url",
    "get_instance",
    "is_entity_recorded",
]


def validate_db_url(db_url: str) -> Any:
    """Validate database URL."""
    # An empty URL falls back to the default database in async_setup
    if not db_url:
        return db_url
    try:
        url = make_url(db_url)
    except (ArgumentError, ValueError) as err:
        raise probatio.Invalid("Invalid database URL") from err
    # SQLAlchemy only rejects these when creating the engine, after the
    # recorder may already have moved away the file named in the URL
    if (
        url.get_backend_name() == "sqlite"
        and url.get_driver_name() == "pysqlite"
        and (url.username or url.password or url.host or url.port)
    ):
        raise probatio.Invalid("Invalid database URL")
    # Don't allow on-memory sqlite databases
    if (
        url.get_backend_name() == "sqlite"
        and not is_file_sqlite_url(url)
        and not ALLOW_IN_MEMORY_DB
    ):
        raise probatio.Invalid("In-memory SQLite database is not supported")

    return db_url


CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN, default=dict): probatio.All(
            cv.deprecated(CONF_PURGE_INTERVAL),
            cv.deprecated(CONF_DB_INTEGRITY_CHECK),
            FILTER_SCHEMA.extend(
                {
                    **SETTINGS_SCHEMA_DICT,
                    probatio.Optional(CONF_PURGE_INTERVAL, default=1): cv.positive_int,
                    probatio.Optional(CONF_DB_URL): probatio.All(
                        cv.string, validate_db_url
                    ),
                    probatio.Optional(
                        CONF_DB_INTEGRITY_CHECK, default=DEFAULT_DB_INTEGRITY_CHECK
                    ): cv.boolean,
                }
            ),
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    conf = config[DOMAIN]
    _filter = convert_include_exclude_filter(conf)
    entity_filter = None if _filter.empty_filter else _filter.get_filter()
    settings = await async_get_settings(
        hass, {key: conf[key] for key in DEFAULT_SETTINGS if key in conf}
    )
    db_url = conf.get(CONF_DB_URL) or get_default_url(hass)
    exclude = conf[CONF_EXCLUDE]
    exclude_event_types: set[EventType[Any] | str] = set(
        exclude.get(CONF_EVENT_TYPES, [])
    )
    if EVENT_STATE_CHANGED in exclude_event_types:
        _LOGGER.error("State change events cannot be excluded, use a filter instead")
        exclude_event_types.remove(EVENT_STATE_CHANGED)
    instance = hass.data[DATA_INSTANCE] = Recorder(
        hass=hass,
        auto_purge=settings[CONF_AUTO_PURGE],
        auto_repack=settings[CONF_AUTO_REPACK],
        keep_days=settings[CONF_PURGE_KEEP_DAYS],
        commit_interval=settings[CONF_COMMIT_INTERVAL],
        uri=db_url,
        db_max_retries=settings[CONF_DB_MAX_RETRIES],
        db_retry_wait=settings[CONF_DB_RETRY_WAIT],
        entity_filter=entity_filter,
        exclude_event_types=exclude_event_types,
    )
    get_instance.cache_clear()
    entity_registry.async_setup(hass)
    entity_options.async_setup(hass)
    recorder_settings.async_setup(hass)
    instance.async_initialize()
    instance.async_register()
    instance.start()
    async_setup_services(hass)
    websocket_api.async_setup(hass)

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


def get_default_url(hass: HomeAssistant) -> str:
    """Return the default URL."""
    return URL.create(
        "sqlite", database=hass.config.path(DEFAULT_DB_FILE)
    ).render_as_string()
