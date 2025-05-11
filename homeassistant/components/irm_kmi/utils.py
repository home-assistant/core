"""Helper functions for use with IRM KMI integration."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_LANGUAGE_OVERRIDE, LANGS
from .data import IrmKmiConfigEntry

_LOGGER = logging.getLogger(__name__)


def disable_from_config(hass: HomeAssistant, config_entry: IrmKmiConfigEntry):
    """Disable the given configuration entry."""

    modify_from_config(hass, config_entry.entry_id, False)


def enable_from_config(hass: HomeAssistant, config_entry: IrmKmiConfigEntry):
    """Enable the given configuration entry."""

    modify_from_config(hass, config_entry.entry_id, True)


def modify_from_config(hass: HomeAssistant, config_entry_id: str, enable: bool):
    """Enable or disable the given configuration entry."""

    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, config_entry_id)
    _LOGGER.info(
        "Trying to %s %s: %d device(s)",
        "enable" if enable else "disable",
        config_entry_id,
        len(devices),
    )
    for device in devices:
        registry.async_update_device(
            device_id=device.id,
            disabled_by=None if enable else dr.DeviceEntryDisabler.INTEGRATION,
        )


def get_config_value(config_entry: IrmKmiConfigEntry, key: str) -> Any:
    """Get the value of key in the configuration.  If options were modified, they take priority."""

    if config_entry.options and key in config_entry.options:
        return config_entry.options[key]
    return config_entry.data[key]


def preferred_language(
    hass: HomeAssistant, config_entry: IrmKmiConfigEntry | None
) -> str:
    """Get the preferred language for the integration if it was overridden by the configuration."""

    if (
        config_entry is None
        or get_config_value(config_entry, CONF_LANGUAGE_OVERRIDE) == "none"
    ):
        return hass.config.language if hass.config.language in LANGS else "en"

    return get_config_value(config_entry, CONF_LANGUAGE_OVERRIDE)
