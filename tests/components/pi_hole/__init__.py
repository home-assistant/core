"""Tests for the pi_hole component."""

from typing import Any
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
    CONF_API_VERSION,
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
ZERO_DATA_V6 = {
    "queries": {
        "total": 0,
        "blocked": 0,
        "percent_blocked": 0,
        "unique_domains": 0,
        "forwarded": 0,
        "cached": 0,
        "frequency": 0,
        "types": dict.fromkeys(
            (
                "A",
                "AAAA",
                "ANY",
                "SRV",
                "SOA",
                "PTR",
                "TXT",
                "NAPTR",
                "MX",
                "DS",
                "RRSIG",
                "DNSKEY",
                "NS",
                "SVCB",
                "HTTPS",
                "OTHER",
            ),
            0,
        ),
        "status": dict.fromkeys(
            (
                "UNKNOWN",
                "GRAVITY",
                "FORWARDED",
                "CACHE",
                "REGEX",
                "DENYLIST",
                "EXTERNAL_BLOCKED_IP",
                "EXTERNAL_BLOCKED_NULL",
                "EXTERNAL_BLOCKED_NXRA",
                "GRAVITY_CNAME",
                "REGEX_CNAME",
                "DENYLIST_CNAME",
                "RETRIED",
                "RETRIED_DNSSEC",
                "IN_PROGRESS",
                "DBBUSY",
                "SPECIAL_DOMAIN",
                "CACHE_STALE",
                "EXTERNAL_BLOCKED_EDE15",
            ),
            0,
        ),
        "replies": dict.fromkeys(
            (
                "UNKNOWN",
                "NODATA",
                "NXDOMAIN",
                "CNAME",
                "IP",
                "DOMAIN",
                "RRNAME",
                "SERVFAIL",
                "REFUSED",
                "NOTIMP",
                "OTHER",
                "DNSSEC",
                "NONE",
                "BLOB",
            ),
            0,
        ),
    },
    "clients": {"active": 0, "total": 0},
    "gravity": {"domains_being_blocked": 0, "last_update": 0},
    "took": 0,
}

V6_RESPONSE_TO_V5_ENPOINT = {
    "error": {
        "key": "bad_request",
        "message": "Bad request",
        "hint": "The API is hosted at pi.hole/api, not pi.hole/admin/api",
    },
    "took": 0.0001430511474609375,
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
API_VERSION = 6
SSL = False
VERIFY_SSL = True

CONFIG_DATA_DEFAULTS = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: DEFAULT_LOCATION,
    CONF_NAME: DEFAULT_NAME,
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    CONF_API_KEY: API_KEY,
    CONF_API_VERSION: API_VERSION,
}

CONFIG_DATA = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_API_KEY: API_KEY,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
    CONF_API_VERSION: API_VERSION,
}

CONFIG_FLOW_USER = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_LOCATION: LOCATION,
    CONF_API_KEY: API_KEY,
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
    CONF_API_VERSION: API_VERSION,
}

CONFIG_ENTRY_WITHOUT_API_KEY = {
    CONF_HOST: f"{HOST}:{PORT}",
    CONF_LOCATION: LOCATION,
    CONF_NAME: NAME,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
    CONF_API_VERSION: API_VERSION,
}
SWITCH_ENTITY_ID = "switch.pi_hole"


def _create_mocked_hole(
    raise_exception: bool = False,
    has_versions: bool = True,
    has_update: bool = True,
    has_data: bool = True,
    hole_version: int = 5,
    api_version: int = 5,
    incorrect_app_password: bool = False,
) -> MagicMock:
    """Return a mocked Hole API object with side effects based on constructor args."""

    instances = []

    def make_mock(**kwargs: Any) -> MagicMock:
        mocked_hole = MagicMock()
        # Set constructor kwargs as attributes
        for key, value in kwargs.items():
            setattr(mocked_hole, key, value)

        async def authenticate_side_effect(*_args, **_kwargs):
            password = getattr(mocked_hole, "password", None)
            if (
                raise_exception
                or incorrect_app_password
                or (api_version == 6 and password == "wrong_password")
            ):
                raise HoleError("Authentication failed: Invalid API token")

        async def get_data_side_effect(*_args, **_kwargs):
            password = getattr(mocked_hole, "password", None)
            api_token = getattr(mocked_hole, "api_token", None)
            if (
                raise_exception
                or incorrect_app_password
                or (api_version == 5 and (not api_token or api_token == "wrong_token"))
                or (api_version == 6 and password == "wrong_password")
            ):
                mocked_hole.data = [] if api_version == 5 else {}
            elif password == "newkey" or api_token == "newkey":
                mocked_hole.data = ZERO_DATA_V6 if api_version == 6 else ZERO_DATA

        mocked_hole.authenticate = AsyncMock(side_effect=authenticate_side_effect)
        mocked_hole.get_data = AsyncMock(side_effect=get_data_side_effect)
        mocked_hole.get_versions = AsyncMock(return_value=None)
        mocked_hole.enable = AsyncMock()
        mocked_hole.disable = AsyncMock()

        # Set versions and version properties
        if has_versions:
            versions = (
                SAMPLE_VERSIONS_WITH_UPDATES
                if has_update
                else SAMPLE_VERSIONS_NO_UPDATES
            )
            mocked_hole.versions = versions
            mocked_hole.ftl_current = versions["FTL_current"]
            mocked_hole.ftl_latest = versions["FTL_latest"]
            mocked_hole.ftl_update = versions["FTL_update"]
            mocked_hole.core_current = versions["core_current"]
            mocked_hole.core_latest = versions["core_latest"]
            mocked_hole.core_update = versions["core_update"]
            mocked_hole.web_current = versions["web_current"]
            mocked_hole.web_latest = versions["web_latest"]
            mocked_hole.web_update = versions["web_update"]
        else:
            mocked_hole.versions = None

        # Set initial data
        if has_data:
            mocked_hole.data = ZERO_DATA_V6 if api_version == 6 else ZERO_DATA
        else:
            mocked_hole.data = [] if api_version == 5 else {}
        instances.append(mocked_hole)
        return mocked_hole

    # Return a factory function for patching
    make_mock.instances = instances
    return make_mock


def _patch_init_hole(mocked_hole):
    """Patch the Hole class in the main integration."""

    def side_effect(*args, **kwargs):
        return mocked_hole(**kwargs)

    return patch("homeassistant.components.pi_hole.Hole", side_effect=side_effect)


def _patch_config_flow_hole(mocked_hole):
    """Patch the Hole class in the config flow."""

    def side_effect(*args, **kwargs):
        return mocked_hole(**kwargs)

    return patch(
        "homeassistant.components.pi_hole.config_flow.Hole", side_effect=side_effect
    )


def _patch_setup_hole():
    """Patch async_setup_entry for the integration."""
    return patch(
        "homeassistant.components.pi_hole.async_setup_entry", return_value=True
    )
