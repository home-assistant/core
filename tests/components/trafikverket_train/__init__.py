"""Tests for the Trafikverket Train integration."""
from __future__ import annotations

from homeassistant.components.trafikverket_ferry.const import (
    CONF_FROM,
    CONF_TIME,
    CONF_TO,
)
from homeassistant.components.trafikverket_train.const import CONF_FILTER_PRODUCT
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS

ENTRY_CONFIG = {
    CONF_API_KEY: "1234567890",
    CONF_FROM: "Stockholm C",
    CONF_TO: "Uppsala C",
    CONF_TIME: None,
    CONF_WEEKDAY: WEEKDAYS,
    CONF_NAME: "Stockholm C to Uppsala C",
}
ENTRY_CONFIG2 = {
    CONF_API_KEY: "1234567890",
    CONF_FROM: "Stockholm C",
    CONF_TO: "Uppsala C",
    CONF_TIME: "11:00:00",
    CONF_WEEKDAY: WEEKDAYS,
    CONF_NAME: "Stockholm C to Uppsala C",
}
OPTIONS_CONFIG = {CONF_FILTER_PRODUCT: "Regionaltåg"}
