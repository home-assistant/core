"""Schemata for ruuvi_gateway."""

import probatio

from homeassistant.const import CONF_HOST, CONF_TOKEN

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_TOKEN): str,
    }
)


def get_config_schema_with_default_host(host: str) -> probatio.Schema:
    """Return a config schema with a default host."""
    return CONFIG_SCHEMA.extend({probatio.Required(CONF_HOST, default=host): str})
