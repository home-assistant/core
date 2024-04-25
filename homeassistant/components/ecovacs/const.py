"""Ecovacs constants."""

from enum import StrEnum

from deebot_client.events import LifeSpan

DOMAIN = "ecovacs"

CONF_CONTINENT = "continent"
CONF_OVERRIDE_REST_URL = "override_rest_url"
CONF_OVERRIDE_MQTT_URL = "override_mqtt_url"
CONF_VERIFY_MQTT_CERTIFICATE = "verify_mqtt_certificate"

SUPPORTED_LIFESPANS = (
    LifeSpan.BLADE,
    LifeSpan.BRUSH,
    LifeSpan.FILTER,
    LifeSpan.LENS_BRUSH,
    LifeSpan.SIDE_BRUSH,
)


class InstanceMode(StrEnum):
    """Instance mode."""

    CLOUD = "cloud"
    SELF_HOSTED = "self_hosted"
