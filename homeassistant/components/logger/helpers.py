"""Helpers for the logger integration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import contextlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import lru_cache
import logging
from typing import Any, cast

from homeassistant.const import EVENT_LOGGING_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import (
    DOMAIN,
    LOGGER_DEFAULT,
    LOGGER_LOGS,
    LOGSEVERITY,
    LOGSEVERITY_NOTSET,
    STORAGE_KEY,
    STORAGE_LOG_KEY,
    STORAGE_VERSION,
)

SAVE_DELAY = 15.0
# At startup, we want to save after a long delay to avoid
# saving while the system is still starting up. If the system
# for some reason restarts quickly, it will still be written
# at the final write event. In most cases we expect startup
# to happen in less than 180 seconds, but if it takes longer
# it's likely delayed because of remote I/O and not local
# I/O so it's fine to save at that point.
SAVE_DELAY_LONG = 180.0


@callback
def async_get_domain_config(hass: HomeAssistant) -> LoggerDomainConfig:
    """Return the domain config."""
    return cast(LoggerDomainConfig, hass.data[DOMAIN])


@callback
def set_default_log_level(hass: HomeAssistant, level: int) -> None:
    """Set the default log level for components."""
    _set_log_level(logging.getLogger(""), level)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)


@callback
def set_log_levels(hass: HomeAssistant, logpoints: Mapping[str, int]) -> None:
    """Set the specified log levels."""
    async_get_domain_config(hass).overrides.update(logpoints)
    for key, value in logpoints.items():
        _set_log_level(logging.getLogger(key), value)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)


def _set_log_level(logger: logging.Logger, level: int) -> None:
    """Set the log level.

    Any logger fetched before this integration is loaded will use old class.
    """
    getattr(logger, "orig_setLevel", logger.setLevel)(level)


def _chattiest_log_level(level1: int, level2: int) -> int:
    """Return the chattiest log level."""
    if level1 == logging.NOTSET:
        return level2
    if level2 == logging.NOTSET:
        return level1
    return min(level1, level2)


async def get_integration_loggers(hass: HomeAssistant, domain: str) -> set[str]:
    """Get loggers for an integration."""
    loggers: set[str] = {f"homeassistant.components.{domain}"}
    with contextlib.suppress(IntegrationNotFound):
        integration = await async_get_integration(hass, domain)
        loggers.add(integration.pkg_path)
        if integration.loggers:
            loggers.update(integration.loggers)
    return loggers


@dataclass(slots=True)
class LoggerSetting:
    """Settings for a single module or integration."""

    level: str
    persistence: str
    type: str


@dataclass(slots=True)
class LoggerDomainConfig:
    """Logger domain config."""

    overrides: dict[str, Any]
    settings: LoggerSettings


class LogPersistance(StrEnum):
    """Log persistence."""

    NONE = "none"
    ONCE = "once"
    PERMANENT = "permanent"


class LogSettingsType(StrEnum):
    """Log settings type."""

    INTEGRATION = "integration"
    MODULE = "module"


class LoggerSettings:
    """Manage log settings."""

    _stored_config: dict[str, dict[str, LoggerSetting]]

    def __init__(self, hass: HomeAssistant, yaml_config: ConfigType) -> None:
        """Initialize log settings."""

        self._yaml_config = yaml_config
        self._default_level = logging.INFO
        if DOMAIN in yaml_config and LOGGER_DEFAULT in yaml_config[DOMAIN]:
            self._default_level = yaml_config[DOMAIN][LOGGER_DEFAULT]
        self._store: Store[dict[str, dict[str, dict[str, Any]]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def async_load(self) -> None:
        """Load stored settings."""
        stored_config = await self._store.async_load()
        if not stored_config:
            self._stored_config = {STORAGE_LOG_KEY: {}}
            return

        def reset_persistence(settings: LoggerSetting) -> LoggerSetting:
            """Reset persistence."""
            if settings.persistence == LogPersistance.ONCE:
                settings.persistence = LogPersistance.NONE
            return settings

        stored_log_config = stored_config[STORAGE_LOG_KEY]
        # Reset domains for which the overrides should only be applied once
        self._stored_config = {
            STORAGE_LOG_KEY: {
                domain: reset_persistence(LoggerSetting(**settings))
                for domain, settings in stored_log_config.items()
            }
        }
        self.async_save(SAVE_DELAY_LONG)

    @callback
    def _async_data_to_save(self) -> dict[str, dict[str, dict[str, str]]]:
        """Generate data to be saved."""
        stored_log_config = self._stored_config[STORAGE_LOG_KEY]
        return {
            STORAGE_LOG_KEY: {
                domain: asdict(settings)
                for domain, settings in stored_log_config.items()
                if settings.persistence
                in (LogPersistance.ONCE, LogPersistance.PERMANENT)
            }
        }

    @callback
    def async_save(self, delay: float = SAVE_DELAY) -> None:
        """Save settings."""
        self._store.async_delay_save(self._async_data_to_save, delay)

    @callback
    def _async_get_logger_logs(self) -> dict[str, int]:
        """Get the logger logs."""
        logger_logs: dict[str, int] = self._yaml_config.get(DOMAIN, {}).get(
            LOGGER_LOGS, {}
        )
        return logger_logs

    async def async_update(
        self, hass: HomeAssistant, domain: str, settings: LoggerSetting
    ) -> None:
        """Update settings."""
        stored_log_config = self._stored_config[STORAGE_LOG_KEY]
        if settings.level == LOGSEVERITY_NOTSET:
            stored_log_config.pop(domain, None)
        else:
            stored_log_config[domain] = settings

        self.async_save()

        if settings.type == LogSettingsType.INTEGRATION:
            loggers = await get_integration_loggers(hass, domain)
        else:
            loggers = {domain}

        combined_logs = {logger: LOGSEVERITY[settings.level] for logger in loggers}
        # Don't override the log levels with the ones from YAML
        # since we want whatever the user is asking for to be honored.

        set_log_levels(hass, combined_logs)

    async def async_get_levels(self, hass: HomeAssistant) -> dict[str, int]:
        """Get combination of levels from yaml and storage."""
        combined_logs = defaultdict(lambda: logging.CRITICAL)
        for domain, settings in self._stored_config[STORAGE_LOG_KEY].items():
            if settings.type == LogSettingsType.INTEGRATION:
                loggers = await get_integration_loggers(hass, domain)
            else:
                loggers = {domain}

            for logger in loggers:
                combined_logs[logger] = LOGSEVERITY[settings.level]

        if yaml_log_settings := self._async_get_logger_logs():
            for domain, level in yaml_log_settings.items():
                combined_logs[domain] = _chattiest_log_level(
                    combined_logs[domain], level
                )

        return dict(combined_logs)


get_logger = lru_cache(maxsize=256)(logging.getLogger)
"""Get a logger.

getLogger uses a threading.RLock, so we cache the result to avoid
locking the threads every time the integrations page is loaded.
"""
