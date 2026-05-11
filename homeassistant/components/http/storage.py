"""Persistent storage for the user-managed HTTP integration config."""

from ipaddress import IPv4Network, IPv6Network
from typing import Any, TypedDict, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

# A separate key from STORAGE_KEY ("http") in __init__.py, which is used for the
# recovery-mode snapshot of the last successfully resolved config. The two stores
# must not share a key.
USER_CONFIG_STORAGE_KEY = "http.config"
USER_CONFIG_STORAGE_VERSION = 1


class HttpUserConfig(TypedDict, total=False):
    """User-managed HTTP config persisted via Store.

    Mirrors the validated output of ``HTTP_SCHEMA`` except ``trusted_proxies`` is
    held as a list of strings for JSON serialization.
    """

    server_host: list[str]
    server_port: int
    ssl_certificate: str
    ssl_peer_certificate: str
    ssl_key: str
    cors_allowed_origins: list[str]
    use_x_forwarded_for: bool
    trusted_proxies: list[str]
    use_x_frame_options: bool
    ip_ban_enabled: bool
    login_attempts_threshold: int
    ssl_profile: str


class HttpConfigStore(Store[HttpUserConfig]):
    """Store for user-managed HTTP config."""


def async_get_store(hass: HomeAssistant) -> HttpConfigStore:
    """Return the user-config Store, private to the integration."""
    return HttpConfigStore(
        hass,
        USER_CONFIG_STORAGE_VERSION,
        USER_CONFIG_STORAGE_KEY,
        private=True,
    )


def to_stored(conf: dict[str, Any]) -> HttpUserConfig:
    """Convert a validated ``HTTP_SCHEMA`` dict into a JSON-serializable form."""
    out: dict[str, Any] = {k: v for k, v in conf.items() if k != "base_url"}
    if "trusted_proxies" in out:
        out["trusted_proxies"] = [
            str(cast(IPv4Network | IPv6Network, n)) for n in out["trusted_proxies"]
        ]
    return cast(HttpUserConfig, out)
