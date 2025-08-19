"""Tests for the pi_hole component."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hole.exceptions import HoleConnectionError, HoleError

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
        "types": {
            "A": 0,
            "AAAA": 0,
            "ANY": 0,
            "SRV": 0,
            "SOA": 0,
            "PTR": 0,
            "TXT": 0,
            "NAPTR": 0,
            "MX": 0,
            "DS": 0,
            "RRSIG": 0,
            "DNSKEY": 0,
            "NS": 0,
            "SVCB": 0,
            "HTTPS": 0,
            "OTHER": 0,
        },
        "status": {
            "UNKNOWN": 0,
            "GRAVITY": 0,
            "FORWARDED": 0,
            "CACHE": 0,
            "REGEX": 0,
            "DENYLIST": 0,
            "EXTERNAL_BLOCKED_IP": 0,
            "EXTERNAL_BLOCKED_NULL": 0,
            "EXTERNAL_BLOCKED_NXRA": 0,
            "GRAVITY_CNAME": 0,
            "REGEX_CNAME": 0,
            "DENYLIST_CNAME": 0,
            "RETRIED": 0,
            "RETRIED_DNSSEC": 0,
            "IN_PROGRESS": 0,
            "DBBUSY": 0,
            "SPECIAL_DOMAIN": 0,
            "CACHE_STALE": 0,
            "EXTERNAL_BLOCKED_EDE15": 0,
        },
        "replies": {
            "UNKNOWN": 0,
            "NODATA": 0,
            "NXDOMAIN": 0,
            "CNAME": 0,
            "IP": 0,
            "DOMAIN": 0,
            "RRNAME": 0,
            "SERVFAIL": 0,
            "REFUSED": 0,
            "NOTIMP": 0,
            "OTHER": 0,
            "DNSSEC": 0,
            "NONE": 0,
            "BLOB": 0,
        },
    },
    "clients": {"active": 0, "total": 0},
    "gravity": {"domains_being_blocked": 0, "last_update": 0},
    "took": 0,
}

FTL_ERROR = {
    "error": {
        "key": "FTLnotrunning",
        "message": "FTL not running",
    }
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
    raise_exception: bool = False,
    has_versions: bool = True,
    has_update: bool = True,
    has_data: bool = True,
    api_version: int = 5,
    incorrect_app_password: bool = False,
    wrong_host: bool = False,
    ftl_error: bool = False,
) -> MagicMock:
    """Return a mocked Hole API object with side effects based on constructor args."""

    instances = []

    def make_mock(**kwargs: Any) -> MagicMock:
        mocked_hole = MagicMock()
        # Set constructor kwargs as attributes
        for key, value in kwargs.items():
            setattr(mocked_hole, key, value)

        async def authenticate_side_effect(*_args, **_kwargs):
            if wrong_host:
                raise HoleConnectionError("Cannot authenticate with Pi-hole: err")
            password = getattr(mocked_hole, "password", None)

            if (
                raise_exception
                or incorrect_app_password
                or api_version == 5
                or (api_version == 6 and password not in ["newkey", "apikey"])
            ):
                if api_version == 6 and (
                    incorrect_app_password or password not in ["newkey", "apikey"]
                ):
                    raise HoleError("Authentication failed: Invalid password")
                raise HoleConnectionError

        async def get_data_side_effect(*_args, **_kwargs):
            """Return data based on the mocked Hole instance state."""
            if wrong_host:
                raise HoleConnectionError("Cannot fetch data from Pi-hole: err")
            password = getattr(mocked_hole, "password", None)
            api_token = getattr(mocked_hole, "api_token", None)
            if (
                raise_exception
                or incorrect_app_password
                or (api_version == 5 and (not api_token or api_token == "wrong_token"))
                or (api_version == 6 and password not in ["newkey", "apikey"])
            ):
                mocked_hole.data = [] if api_version == 5 else {}
            elif password in ["newkey", "apikey"] or api_token in ["newkey", "apikey"]:
                mocked_hole.data = ZERO_DATA_V6 if api_version == 6 else ZERO_DATA

        async def ftl_side_effect():
            mocked_hole.data = FTL_ERROR

        mocked_hole.authenticate = AsyncMock(side_effect=authenticate_side_effect)
        mocked_hole.get_data = AsyncMock(side_effect=get_data_side_effect)

        if ftl_error:
            # two unauthenticated instances are created in `determine_api_version` before aync_try_connect is called
            if len(instances) > 1:
                mocked_hole.get_data = AsyncMock(side_effect=ftl_side_effect)
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
