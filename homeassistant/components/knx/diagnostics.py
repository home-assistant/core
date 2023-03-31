"""Diagnostics support for KNX."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import CONFIG_SCHEMA
from .const import (
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_PASSWORD,
    DOMAIN,
)

TO_REDACT = {
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    knx_module = hass.data[DOMAIN]
    diag["xknx"] = {
        "version": knx_module.xknx.version,
        "current_address": str(knx_module.xknx.current_address),
    }

    diag["config_entry_data"] = async_redact_data(dict(config_entry.data), TO_REDACT)

    raw_config = await conf_util.async_hass_config_yaml(hass)
    diag["configuration_yaml"] = raw_config.get(DOMAIN)
    try:
        CONFIG_SCHEMA(raw_config)
    except vol.Invalid as ex:
        diag["configuration_error"] = str(ex)
    else:
        diag["configuration_error"] = None

    return diag
