"""Tests for the Transports Metropolitans de Barcelona integration."""

from homeassistant.components.tmb.const import (
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_FROM_LATITUDE,
    CONF_FROM_LONGITUDE,
    CONF_LINE,
    CONF_SERVICE,
    CONF_STOP,
    CONF_TO_LATITUDE,
    CONF_TO_LONGITUDE,
    SERVICE_IBUS,
    SERVICE_PLANNER,
)
from homeassistant.const import CONF_NAME

USER_INPUT_SELECT_IBUS = {
    CONF_SERVICE: SERVICE_IBUS,
}

USER_INPUT_SELECT_PLANNER = {
    CONF_SERVICE: SERVICE_PLANNER,
}

USER_INPUT_IBUS = {
    CONF_NAME: "Gran Via",
    CONF_LINE: "H12",
    CONF_STOP: "1209",
}

USER_INPUT_PLANNER = {
    CONF_NAME: "From A to B",
    CONF_FROM_LATITUDE: "41.3872511",
    CONF_FROM_LONGITUDE: "2.1663221",
    CONF_TO_LATITUDE: "41.4134119",
    CONF_TO_LONGITUDE: "2.2253607",
}

MOCK_CONF = {
    CONF_APP_ID: "mock_app_id",
    CONF_APP_KEY: "mock_app_key",
}
