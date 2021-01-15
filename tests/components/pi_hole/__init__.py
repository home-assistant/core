"""Tests for the pi_hole component."""
from unittest.mock import AsyncMock, MagicMock, patch

from hole.exceptions import HoleError

from homeassistant.components.pi_hole.const import CONF_LOCATION
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

ZERO_DATA = {
    "ads_blocked_today": 0,
    "ads_percentage_today": 0,
    "clients_ever_seen": 0,
    "dns_queries_today": 0,
    "domains_being_blocked": 0,
    "queries_cached": 0,
    "queries_forwarded": 0,
    "status": "disabled",
    "unique_clients": 0,
    "unique_domains": 0,
}

HOST = "1.2.3.4"
PORT = 80
LOCATION = "location"
NAME = "Pi hole"
API_KEY = "apikey"
SSL = False
VERIFY_SSL = True

CONF_DATA = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_API_KEY: API_KEY,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_API_KEY: API_KEY,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

SWITCH_ENTITY_ID = "switch.pi_hole"


def _create_mocked_hole(raise_exception=False):
    mocked_hole = MagicMock()
    type(mocked_hole).get_data = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).enable = AsyncMock()
    type(mocked_hole).disable = AsyncMock()
    mocked_hole.data = ZERO_DATA
    return mocked_hole


def _patch_init_hole(mocked_hole):
    return patch("homeassistant.components.pi_hole.Hole", return_value=mocked_hole)


def _patch_config_flow_hole(mocked_hole):
    return patch(
        "homeassistant.components.pi_hole.config_flow.Hole", return_value=mocked_hole
    )
