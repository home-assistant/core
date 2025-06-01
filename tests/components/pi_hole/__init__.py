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
    raise_exception=False,
    has_versions=True,
    has_update=True,
    has_data=True,
    api_version=6,
    incorrect_app_password=False,
):
    mocked_hole = MagicMock()
    type(mocked_hole).authenticate = AsyncMock(
        side_effect=HoleError("")
        if raise_exception or api_version == 5 or incorrect_app_password
        else None
    )
    type(mocked_hole).get_data = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).get_versions = AsyncMock(
        side_effect=HoleError("") if raise_exception else None
    )
    type(mocked_hole).enable = AsyncMock()
    type(mocked_hole).disable = AsyncMock()
    if has_data and api_version == 5:
        mocked_hole.data = ZERO_DATA
    # if the api is actually V6 and the app password is incorrect, the try at the V5 endpoint will return this warning
    if has_data and api_version == 6 and incorrect_app_password:
        mocked_hole.data = V6_RESPONSE_TO_V5_ENPOINT
    if has_data and api_version == 6 and not incorrect_app_password:
        mocked_hole.data = ZERO_DATA_V6
    if not has_data:
        mocked_hole.data = []
    if has_versions:
        if has_update:
            versions = SAMPLE_VERSIONS_WITH_UPDATES
        else:
            versions = SAMPLE_VERSIONS_NO_UPDATES
        mocked_hole.versions = versions
        # Patch all version properties to return real values
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
