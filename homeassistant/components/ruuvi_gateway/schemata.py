"""Schemata for ruuvi_gateway."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_TOKEN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TOKEN): str,
    }
)


def get_config_schema_with_default_host(host: str) -> vol.Schema:
    """Return a config schema with a default host."""
    return CONFIG_SCHEMA.extend({vol.Required(CONF_HOST, default=host): str})
