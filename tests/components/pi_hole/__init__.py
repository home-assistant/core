"""Tests for the pi_hole component."""

from unittest.mock import AsyncMock, MagicMock, patch

from hole.exceptions import HoleError

from homeassistant.components.pi_hole.const import (
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_LOCATION,
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

SAMPLE_VERSIONS_WITH_UPDATES = {
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

SAMPLE_VERSIONS_NO_UPDATES = {
    "core_current": "v5.5",
    "core_latest": "v5.5",
    "core_update": False,
    "web_current": "v5.7",
    "web_latest": "v5.7",
    "web_update": False,
    "FTL_current": "v5.10",
    "FTL_latest": "v5.10",
    "FTL_update": False,
}

HOST = "1.2.3.4"
PORT = 80
LOCATION = "location"
NAME = "Pi hole"
API_KEY = "apikey"
SSL = False
VERIFY_SSL = True

CONFIG_DATA_DEFAULTS = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: DEFAULT_LOCATION,
    CONF_NAME: DEFAULT_NAME,
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    CONF_API_KEY: API_KEY,
}

CONFIG_DATA = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_API_KEY: API_KEY,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

CONFIG_FLOW_USER = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

CONFIG_FLOW_API_KEY = {
    CONF_API_KEY: API_KEY,
}

CONFIG_ENTRY_WITH_API_KEY = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_API_KEY: API_KEY,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

CONFIG_ENTRY_WITHOUT_API_KEY = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}
SWITCH_ENTITY_ID = "switch.pi_hole"


def _create_mocked_hole(
    raise_exception=False, has_versions=True, has_update=True, has_data=True
):
    mocked_hole = MagicMock()
    type(mocked_hole).get_data = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).get_versions = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).enable = AsyncMock()
    type(mocked_hole).disable = AsyncMock()
    if has_data:
        mocked_hole.data = ZERO_DATA
    else:
        mocked_hole.data = []
    if has_versions:
        if has_update:
            mocked_hole.versions = SAMPLE_VERSIONS_WITH_UPDATES
        else:
            mocked_hole.versions = SAMPLE_VERSIONS_NO_UPDATES
    else:
        mocked_hole.versions = None
    return mocked_hole


def _patch_init_hole(mocked_hole):
    return patch("homeassistant.components.pi_hole.Hole", return_value=mocked_hole)


def _patch_config_flow_hole(mocked_hole):
    return patch(
        "homeassistant.components.pi_hole.config_flow.Hole", return_value=mocked_hole
    )


def _patch_setup_hole():
    return patch(
        "homeassistant.components.pi_hole.async_setup_entry", return_value=True
    )
