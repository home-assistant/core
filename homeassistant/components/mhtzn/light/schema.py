"""Shared schema code."""
import voluptuous as vol

CONF_SCHEMA = "schema"

MQTT_LIGHT_SCHEMA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCHEMA, default="json"): vol.All(
            vol.Lower, vol.Any("json")
        )
    }
)
