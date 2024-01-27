"""Ecovacs constants."""

from enum import StrEnum

DOMAIN = "ecovacs"

CONF_CONTINENT = "continent"


class InstanceMode(StrEnum):
    """Instance mode."""

    CLOUD = "cloud"
    SELF_HOSTED = "self_hosted"
