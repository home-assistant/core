"""Shared schema code."""

import probatio

from ..const import CONF_SCHEMA

MQTT_LIGHT_SCHEMA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SCHEMA, default="basic"): probatio.All(
            probatio.Lower, probatio.Any("basic", "json", "template")
        )
    }
)
