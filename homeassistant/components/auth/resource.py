"""Resource indicators for Home Assistant's instance-wide OAuth grants."""

from urllib.parse import urlsplit

from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url


def normalize_resource(hass: HomeAssistant, resource: str | None) -> str | None:
    """Validate an optional resource against the advertised Home Assistant origin."""
    if resource is None:
        return None

    if any(ord(char) <= 32 or ord(char) == 127 for char in resource):
        raise ValueError("Invalid resource")

    url = URL(resource)
    try:
        trusted_url = URL(get_url(hass, require_current_request=True))
    except NoURLAvailableError as err:
        raise ValueError("No trusted resource available") from err

    if (
        url.scheme != "https"
        or url.user is not None
        or urlsplit(resource).path not in ("", "/")
        or "?" in resource
        or "#" in resource
        or (url.scheme, url.host, url.port)
        != (trusted_url.scheme, trusted_url.host, trusted_url.port)
    ):
        raise ValueError("Invalid resource")

    origin = trusted_url.origin()
    if origin.is_default_port():
        origin = origin.with_port(None)
    return str(origin)
