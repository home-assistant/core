"""Ecovacs constants."""
from deebot_client.events import LifeSpan

DOMAIN = "ecovacs"

CONF_CONTINENT = "continent"

SUPPORTED_LIFESPANS = (
    LifeSpan.BRUSH,
    LifeSpan.FILTER,
    LifeSpan.SIDE_BRUSH,
)
