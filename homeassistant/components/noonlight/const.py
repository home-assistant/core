"""Constants for the Noonlight integration."""

from typing import Final

from homeassistant.const import (  # noqa: F401
    CONF_ADDRESS,
    CONF_API_TOKEN,
    CONF_NAME,
    CONF_STATE,
    STATE_IDLE,
)

DOMAIN: Final = "noonlight"

PLATFORMS: Final = ["binary_sensor", "sensor"]

# --- API ----------------------------------------------------------------------

API_BASE_PROD: Final = "https://api.noonlight.com"
# Sandbox is Noonlight's developer/testing instance. There is no separate
# "dev" hostname — sandbox is the dev environment.
API_BASE_SANDBOX: Final = "https://api-sandbox.noonlight.com"

# Selectable environments. Each named env maps to a base URL above; ``custom``
# lets the user paste an arbitrary base URL (e.g. a private endpoint).
ENV_PRODUCTION: Final = "production"
ENV_SANDBOX: Final = "sandbox"
ENV_CUSTOM: Final = "custom"

ENVIRONMENTS: Final = [ENV_PRODUCTION, ENV_SANDBOX, ENV_CUSTOM]

ENVIRONMENT_BASE_URLS: Final = {
    ENV_PRODUCTION: API_BASE_PROD,
    ENV_SANDBOX: API_BASE_SANDBOX,
}

# Environments that never reach real responders. Used to decide whether the
# safety acknowledgment is required and which env ``test_dispatch`` borrows.
NON_PRODUCTION_ENVIRONMENTS: Final = {ENV_SANDBOX}

DEFAULT_ENVIRONMENT: Final = ENV_SANDBOX


def resolve_base_url(environment: str, custom_base_url: str | None) -> str:
    """Resolve a base URL from an environment label + optional override.

    For ``custom`` the override is required; the named environments ignore it.
    Any trailing slash is stripped so path concatenation stays clean.
    """
    if environment == ENV_CUSTOM:
        if not custom_base_url:
            raise ValueError("custom environment requires a base URL")
        return custom_base_url.rstrip("/")
    try:
        return ENVIRONMENT_BASE_URLS[environment].rstrip("/")
    except KeyError as err:
        raise ValueError(f"unknown environment: {environment}") from err


# --- Config entry: data keys --------------------------------------------------

CONF_ENVIRONMENT: Final = "environment"
# Only consulted when ``environment == custom``; holds the override base URL.
CONF_BASE_URL: Final = "base_url"

CONF_PHONE: Final = "phone"
CONF_CITY: Final = "city"
CONF_ZIP: Final = "zip"
# Optional human label for this property/site. Sent to Noonlight as owner_id
# and folded into the responder instructions so multi-property setups can tell
# which site raised an alarm.
CONF_LOCATION_ID: Final = "location_id"

CONF_SAFETY_ACK: Final = "safety_ack"

# --- Config entry: option keys ------------------------------------------------

CONF_DEFAULT_ENTRY_DELAY: Final = "default_entry_delay_seconds"
CONF_DEDUPE_SECONDS: Final = "dedupe_seconds"
CONF_SERVICES_GRANTED: Final = "services_granted"
CONF_HEARTBEAT_MINUTES: Final = "heartbeat_minutes"

# --- Defaults -----------------------------------------------------------------

DEFAULT_ENTRY_DELAY: Final = 30
MIN_ENTRY_DELAY: Final = 0
MAX_ENTRY_DELAY: Final = 120

DEFAULT_DEDUPE_SECONDS: Final = 300

# How often we poll Noonlight for status while a dispatch is active.
POLL_INTERVAL: Final = 30  # seconds

# Idle heartbeat: how often (minutes) to probe Noonlight for reachability +
# valid credentials so failures surface BEFORE an emergency, not during one.
# Default idle-heartbeat cadence. The probe is a harmless read that returns a
# 404 (which is the *healthy* signal: reachable + authorized). 0 disables it.
DEFAULT_HEARTBEAT_MINUTES: Final = 60
MIN_HEARTBEAT_MINUTES: Final = 0  # 0 = disabled
MAX_HEARTBEAT_MINUTES: Final = 1440
# Consecutive heartbeat failures before raising a Repair issue (avoids
# alerting on a single transient blip).
HEARTBEAT_FAILURE_THRESHOLD: Final = 2
# Bogus alarm id used for the side-effect-free probe (GET status → 404 means
# reachable + authorized; 401 means the token is bad). Never creates an alarm.
HEARTBEAT_PROBE_ID: Final = "heartbeat-probe"

# Time the machine lingers in ``canceled`` before settling back to ``idle``.
CANCEL_SETTLE_SECONDS: Final = 2

# --- Caller location validation ----------------------------------------------

# Valid 2-letter codes Noonlight accepts for the caller location (US states +
# DC + territories). Noonlight rejects anything else ("Virginia", "va", typos).
US_STATE_CODES: Final = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",  # codespell:ignore
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
        "PR",
        "GU",
        "VI",
        "AS",
        "MP",
    }
)

# --- Noonlight service identifiers -------------------------------------------

SERVICE_POLICE: Final = "police"
SERVICE_FIRE: Final = "fire"
SERVICE_MEDICAL: Final = "medical"

ALL_NOONLIGHT_SERVICES: Final = [SERVICE_POLICE, SERVICE_FIRE, SERVICE_MEDICAL]

# --- HA service names ---------------------------------------------------------

SVC_DISPATCH_POLICE: Final = "dispatch_police"
SVC_DISPATCH_FIRE: Final = "dispatch_fire"
SVC_DISPATCH_MEDICAL: Final = "dispatch_medical"
SVC_DISPATCH_ALL: Final = "dispatch_all"
SVC_CANCEL: Final = "cancel"
SVC_TEST_DISPATCH: Final = "test_dispatch"

# Maps each dispatch HA service to the Noonlight services it requests.
DISPATCH_SERVICE_MAP: Final = {
    SVC_DISPATCH_POLICE: [SERVICE_POLICE],
    SVC_DISPATCH_FIRE: [SERVICE_FIRE],
    SVC_DISPATCH_MEDICAL: [SERVICE_MEDICAL],
    SVC_DISPATCH_ALL: ALL_NOONLIGHT_SERVICES,
}

# --- Service call fields ------------------------------------------------------

ATTR_ENTRY_DELAY: Final = "entry_delay_seconds"
ATTR_ACCOUNT: Final = "account"
ATTR_REASON: Final = "reason"
# Free-text context passed through to Noonlight's instructions.entry (e.g.
# which sensor triggered the dispatch).
ATTR_INSTRUCTIONS: Final = "instructions"

# --- Dispatch state machine ---------------------------------------------------

STATE_PENDING: Final = "pending"
STATE_DISPATCHED: Final = "dispatched"
STATE_CANCELED: Final = "canceled"
STATE_ERROR: Final = "error"

DISPATCH_STATES: Final = [
    STATE_IDLE,
    STATE_PENDING,
    STATE_DISPATCHED,
    STATE_CANCELED,
    STATE_ERROR,
]

# --- Event types (audit log + last_event sensor) ------------------------------

EVENT_DISPATCH_REQUESTED: Final = "dispatch_requested"
EVENT_DISPATCH_FIRED: Final = "dispatch_fired"
EVENT_DISPATCH_CANCELED: Final = "dispatch_canceled"
EVENT_DISPATCH_DEDUPED: Final = "dispatch_deduped"
EVENT_STATUS_UPDATED: Final = "status_updated"
EVENT_TEST_DISPATCH: Final = "test_dispatch"
EVENT_ERROR: Final = "error"
EVENT_CLEARED: Final = "cleared"

# --- Storage ------------------------------------------------------------------

STORAGE_VERSION: Final = 1
STORAGE_KEY_TEMPLATE: Final = f"{DOMAIN}.{{entry_id}}"

AUDIT_FILE_TEMPLATE: Final = f"{DOMAIN}_audit_{{entry_id}}.jsonl"
# Rotate the audit log once it grows past this size (bytes). One rotation kept.
AUDIT_MAX_BYTES: Final = 1_000_000

# --- Repair issues ------------------------------------------------------------

ISSUE_AUTH_FAILED: Final = "auth_failed"
ISSUE_NETWORK_FAILED: Final = "network_failed"
ISSUE_UNEXPECTED_RESPONSE: Final = "unexpected_response"
