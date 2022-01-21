"""Tests for the pi_hole component."""
from unittest.mock import AsyncMock, MagicMock, patch

from hole.exceptions import HoleError

from homeassistant.components.pi_hole.const import CONF_LOCATION, CONF_STATISTICS_ONLY
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

SAMPLE_VERSIONS = {
    "core_current": "v5.5",
    "core_latest": "v5.6",
    "core_update": True,
    "web_current": "v5.7",
    "web_latest": "v5.8",
    "web_update": True,
    "FTL_current": "v5.10",
    "FTL_latest": "v5.11",
    "FTL_update": True,
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

CONF_CONFIG_FLOW_USER = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_STATISTICS_ONLY: False,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

CONF_CONFIG_FLOW_API_KEY = {
    CONF_API_KEY: API_KEY,
}

CONF_CONFIG_ENTRY = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_STATISTICS_ONLY: False,
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
    type(mocked_hole).get_versions = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).enable = AsyncMock()
    type(mocked_hole).disable = AsyncMock()
    mocked_hole.data = ZERO_DATA
    mocked_hole.versions = SAMPLE_VERSIONS
    return mocked_hole


def _patch_init_hole(mocked_hole):
    return patch("homeassistant.components.pi_hole.Hole", return_value=mocked_hole)


def _patch_config_flow_hole(mocked_hole):
    return patch(
        "homeassistant.components.pi_hole.config_flow.Hole", return_value=mocked_hole
    )
