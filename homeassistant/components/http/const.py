"""HTTP specific constants."""

from typing import Final

from aiohttp.web import Request

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

DOMAIN: Final = "http"

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"

CONF_SERVER_HOST: Final = "server_host"
CONF_SERVER_PORT: Final = "server_port"
CONF_BASE_URL: Final = "base_url"
CONF_SSL_CERTIFICATE: Final = "ssl_certificate"
CONF_SSL_PEER_CERTIFICATE: Final = "ssl_peer_certificate"
CONF_SSL_KEY: Final = "ssl_key"
CONF_CORS_ORIGINS: Final = "cors_allowed_origins"
CONF_USE_X_FORWARDED_FOR: Final = "use_x_forwarded_for"
CONF_USE_X_FRAME_OPTIONS: Final = "use_x_frame_options"
CONF_TRUSTED_PROXIES: Final = "trusted_proxies"
CONF_LOGIN_ATTEMPTS_THRESHOLD: Final = "login_attempts_threshold"
CONF_IP_BAN_ENABLED: Final = "ip_ban_enabled"
CONF_SSL_PROFILE: Final = "ssl_profile"

SSL_MODERN: Final = "modern"
SSL_INTERMEDIATE: Final = "intermediate"

ENV_SETUP_PORT: Final = "SETUP_PORT"

# Cast to be able to load custom cards.
# My to be able to check url and version info.
DEFAULT_CORS: Final[list[str]] = ["https://cast.home-assistant.io"]
NO_LOGIN_ATTEMPT_THRESHOLD: Final = -1

ATTR_CONFIG = "config"


def is_supervisor_unix_socket_request(request: Request) -> bool:
    """Check if request arrived over the Supervisor Unix socket."""
    if (transport := request.transport) is None:
        return False
    if (http := request.app[KEY_HASS].http) is None or (
        supervisor_path := http.supervisor_unix_socket_path
    ) is None:
        return False
    sockname: str | None = transport.get_extra_info("sockname")
    return sockname == str(supervisor_path)
