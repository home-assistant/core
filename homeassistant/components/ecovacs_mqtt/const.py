"""Const module."""
from __future__ import annotations

from enum import StrEnum

from homeassistant.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

DOMAIN = "ecovacs_mqtt"


class Mode(StrEnum):
    """Enum for modes."""

    CLOUD = "cloud"
    SELF_HOSTED = "self_hosted"


# Self hosted (bumper) has no auth and serves the urls for all countries/continents
SELF_HOSTED_CONFIGURATION = {
    CONF_COUNTRY: "it",
    CONF_PASSWORD: "password",
    CONF_USERNAME: "username",
    CONF_VERIFY_SSL: False,  # required it is using self signed certificates
}
