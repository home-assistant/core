"""Shared schema code."""
import voluptuous as vol

from ..const import CONF_SCHEMA

MQTT_LIGHT_SCHEMA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCHEMA, default="basic"): vol.All(
            vol.Lower, vol.Any("basic", "json", "template")
        )
    }
)
