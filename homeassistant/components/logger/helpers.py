"""Helpers for the logger integration."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import contextlib
from dataclasses import asdict, dataclass
import logging
from typing import cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import (
    DOMAIN,
    EVENT_LOGGING_CHANGED,
    LOGGER_DEFAULT,
    LOGGER_LOGS,
    LOGSEVERITY,
    STORAGE_KEY,
    STORAGE_VERSION,
)


@callback
def set_default_log_level(hass: HomeAssistant, level: int) -> None:
    """Set the default log level for components."""
    _set_log_level(logging.getLogger(""), level)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)


@callback
def set_log_levels(hass: HomeAssistant, logpoints: Mapping[str, int]) -> None:
    """Set the specified log levels."""
    hass.data[DOMAIN]["overrides"].update(logpoints)
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


async def get_integration_loggers(hass: HomeAssistant, domain: str) -> list[str]:
    """Get loggers for an integration."""
    loggers = [f"homeassistant.components.{domain}"]
    with contextlib.suppress(IntegrationNotFound):
        integration = await async_get_integration(hass, domain)
        if integration.loggers:
            loggers.extend(integration.loggers)
    return loggers


@dataclass
class LoggerSetting:
    """Settings for a single module or integration."""

    level: str
    persistence: str
    type: str


class LoggerSettings:
    """Manage log settings."""

    _stored_config: dict[str, dict[str, LoggerSetting]]

    def __init__(self, hass: HomeAssistant, yaml_config: ConfigType) -> None:
        """Initialize log settings."""

        self._yaml_config = yaml_config
        self._default_level = logging.INFO
        if DOMAIN in yaml_config:
            self._default_level = yaml_config[DOMAIN][LOGGER_DEFAULT]
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load stored settings."""

        def reset_persistence(settings: LoggerSetting) -> LoggerSetting:
            """Reset persistence."""
            if settings.persistence == "once":
                settings.persistence = "none"
            return settings

        stored_config = await self._store.async_load()
        if stored_config:
            # Reset domains for which the overrides should only be applied once
            self._stored_config = {
                "logs": {
                    domain: reset_persistence(LoggerSetting(**settings))
                    for domain, settings in cast(dict, stored_config)["logs"].items()
                }
            }
            await self._store.async_save(self._async_data_to_save())
        else:
            self._stored_config = {"logs": {}}

    @callback
    def _async_data_to_save(self) -> dict[str, dict[str, dict[str, str]]]:
        """Generate data to be saved."""
        return {
            "logs": {
                domain: asdict(settings)
                for domain, settings in self._stored_config["logs"].items()
                if settings.persistence in ("once", "permanent")
            }
        }

    @callback
    def async_save(self) -> None:
        """Save settings."""
        self._store.async_delay_save(self._async_data_to_save, 15)

    async def async_update(
        self, hass: HomeAssistant, domain: str, settings: LoggerSetting
    ) -> None:
        """Update settings."""
        if settings.level == "NOTSET":
            self._stored_config["logs"].pop(domain, None)
        else:
            self._stored_config["logs"][domain] = settings
        self.async_save()

        if settings.type == "integration":
            loggers = await get_integration_loggers(hass, domain)
        else:
            loggers = [domain]

        combined_logs = {}
        for logger in loggers:
            combined_logs[logger] = LOGSEVERITY[settings.level]

        # Consider potentially chattier log levels already set in configuration.yaml
        if DOMAIN in self._yaml_config and LOGGER_LOGS in self._yaml_config[DOMAIN]:
            yaml_log_settings = self._yaml_config[DOMAIN][LOGGER_LOGS]
            for logger in loggers:
                combined_logs[logger] = _chattiest_log_level(
                    combined_logs[logger],
                    yaml_log_settings.get(logger, logging.NOTSET),
                )
        set_log_levels(hass, combined_logs)

    async def async_get_levels(self, hass: HomeAssistant) -> dict[str, int]:
        """Get combination of levels from yaml and storage."""
        combined_logs = defaultdict(lambda: logging.CRITICAL)
        for domain, settings in self._stored_config["logs"].items():
            if settings.type == "integration":
                loggers = await get_integration_loggers(hass, domain)
            else:
                loggers = [domain]

            for logger in loggers:
                combined_logs[logger] = LOGSEVERITY[settings.level]

        if DOMAIN in self._yaml_config and LOGGER_LOGS in self._yaml_config[DOMAIN]:
            for domain, level in self._yaml_config[DOMAIN][LOGGER_LOGS].items():
                combined_logs[domain] = _chattiest_log_level(
                    combined_logs[domain], level
                )

        return dict(combined_logs)
