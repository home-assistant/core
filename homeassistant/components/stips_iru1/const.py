"""Constants for STIPS IRU1 integration."""

DOMAIN = "stips_iru1"
PLATFORMS = ["climate"]

CONF_API_HOST = "api_host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_AREA_ID = "area_id"
CONF_DEVICE_UNIQUE_NAME = "device_unique_name"
CONF_DEVICE_IP = "device_ip"

DEFAULT_API_HOST = "stips.api.staging.visionalization.net"

DATA_CLIENT = "client"


def normalize_remote_type(remote_type: str | None) -> str:
    """Normalize STIPS remote type labels for comparisons."""
    if not remote_type:
        return ""
    return remote_type.strip().lower().replace(" ", "")


def is_protocol_ac(remote_type: str | None) -> bool:
    """True for backend IRac remotes (type ``AC``), not LearnedAc."""
    return normalize_remote_type(remote_type) == "ac"


def is_learned_ac(remote_type: str | None) -> bool:
    """True for LearnedAc remotes built from learned signal sets."""
    return normalize_remote_type(remote_type) == "learnedac"


def remote_uses_signal_buttons(remote_type: str | None) -> bool:
    """True if HA should expose a signal-based `remote.*` for this STIPS remote.

    Protocol AC remotes are controlled via IRac status (type/model/power/mode/...), not
    per-button raw signals. LearnedAc / TV / LearnedTv (and similar) use downloaded signals.
    """
    t = normalize_remote_type(remote_type)
    if not t:
        return True
    if t == "learnedac":
        return False
    if t.startswith("learned"):
        return True
    return t != "ac"
