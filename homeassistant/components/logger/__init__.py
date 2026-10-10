"""Support for setting the level of logging for components."""

import logging
import re
from typing import override

import probatio

from homeassistant.const import EVENT_LOGGING_CHANGED  # noqa: F401
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import (  # noqa: F401
    DOMAIN,
    LOGGER_DEFAULT,
    LOGGER_FILTERS,
    LOGGER_LOGS,
    LOGSEVERITY,
    SERVICE_SET_LEVEL,
)
from .helpers import (
    DATA_LOGGER,
    VALID_LOG_LEVEL,
    LoggerDomainConfig,
    LoggerSettings,
    _clear_logger_overwrites,  # noqa: F401
    set_default_log_level,
    set_log_levels,
)
from .services import async_setup_services

# Home Assistant moved from httpx to httpx2, which logs under new logger names.
RENAMED_LOGGERS = {"httpx": "httpx2", "httpcore": "httpcore2"}

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(LOGGER_DEFAULT): VALID_LOG_LEVEL,
                probatio.Optional(LOGGER_LOGS): probatio.Schema(
                    {cv.string: VALID_LOG_LEVEL}
                ),
                probatio.Optional(LOGGER_FILTERS): probatio.Schema(
                    {cv.string: [cv.is_regex]}
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the logger component."""

    settings = LoggerSettings(hass, config)

    domain_config = hass.data[DATA_LOGGER] = LoggerDomainConfig({}, settings)
    logging.setLoggerClass(_get_logger_class(domain_config.overrides))

    websocket_api.async_load_websocket_api(hass)

    await settings.async_load()

    # Set default log severity and filter
    logger_config = config.get(DOMAIN, {})
    _async_check_renamed_loggers(hass, logger_config)

    if LOGGER_DEFAULT in logger_config:
        set_default_log_level(hass, logger_config[LOGGER_DEFAULT])

    if LOGGER_FILTERS in logger_config:
        log_filters: dict[str, list[re.Pattern]] = logger_config[LOGGER_FILTERS]
        for key, value in log_filters.items():
            _add_log_filter(logging.getLogger(key), value)

    # Combine log levels configured in configuration.yaml
    # with log levels set by frontend
    combined_logs = await settings.async_get_levels(hass)
    set_log_levels(hass, combined_logs)

    async_setup_services(hass)

    return True


def _renamed_logger(name: str) -> str | None:
    """Return the new name of a renamed logger, or None if not renamed."""
    for old, new in RENAMED_LOGGERS.items():
        if name == old or name.startswith(f"{old}."):
            return f"{new}{name.removeprefix(old)}"
    return None


@callback
def _async_check_renamed_loggers(
    hass: HomeAssistant, logger_config: ConfigType
) -> None:
    """Create a repair issue if the config uses renamed logger names."""
    renames = {
        name: new_name
        for section in (LOGGER_LOGS, LOGGER_FILTERS)
        for name in logger_config.get(section, {})
        if (new_name := _renamed_logger(name))
    }
    if not renames:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        "renamed_loggers",
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="renamed_loggers",
        translation_placeholders={
            "loggers": "\n".join(
                f"- `{old}` → `{new}`" for old, new in sorted(renames.items())
            )
        },
    )


def _add_log_filter(logger: logging.Logger, patterns: list[re.Pattern]) -> None:
    """Add a Filter to the logger based on a regexp of the filter_str."""

    def filter_func(logrecord: logging.LogRecord) -> bool:
        return not any(p.search(logrecord.getMessage()) for p in patterns)

    logger.addFilter(filter_func)


def _get_logger_class(hass_overrides: dict[str, int]) -> type[logging.Logger]:
    """Create a logger subclass.

    logging.setLoggerClass checks if it is a subclass of Logger and
    so we cannot use partial to inject hass_overrides.
    """

    class HassLogger(logging.Logger):
        """Home Assistant aware logger class."""

        @override
        def setLevel(self, level: int | str) -> None:
            """Set the log level unless overridden."""
            if self.name in hass_overrides:
                return

            super().setLevel(level)

        def orig_setLevel(self, level: int | str) -> None:
            """Set the log level."""
            super().setLevel(level)

    return HassLogger
