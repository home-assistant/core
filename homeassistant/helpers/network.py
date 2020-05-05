"""Network helpers."""
from ipaddress import ip_address
from typing import Optional, cast

import yarl

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.util import get_local_ip
from homeassistant.util.network import (
    is_ip_address,
    is_local,
    is_loopback,
    normalize_url,
)


class NoURLAvailableError(HomeAssistantError):
    """An URL to the Home Assistant instance is not available."""


@bind_hass
@callback
def async_get_url(
    hass: HomeAssistant,
    *,
    require_ssl: bool = False,
    require_standard_port: bool = False,
    allow_local: bool = True,
) -> str:
    """Get a URL to this instance."""
    # Return internal URL when available and matches requested citeria
    if allow_local and hass.config.internal_url:
        internal_url = yarl.URL(hass.config.internal_url)
        if (not require_ssl or internal_url.scheme == "https") and (
            not require_standard_port or internal_url.is_default_port()
        ):
            return normalize_url(str(internal_url))

    # Return IP if local is allowed and it matches citeria requested.
    # This cannot be used if SSL is required, as IP based will always result
    # in a invalid SSL certificate.
    if (
        allow_local
        and not require_ssl
        and hass.config.api is not None
        and not hass.config.api.use_ssl
    ):
        ip_url = yarl.URL.build(
            scheme="http", host=get_local_ip(), port=hass.config.api.port
        )
        if not is_loopback(ip_address(ip_url.host)) and (
            not require_standard_port or ip_url.is_default_port()
        ):
            return normalize_url(str(ip_url))

    # Return user set external URL if it matches the requested citeria
    if hass.config.external_url:
        external_url = yarl.URL(hass.config.external_url)
        if (not require_standard_port or external_url.is_default_port()) and (
            not require_ssl
            or (
                external_url.scheme == "https"
                and not is_ip_address(str(external_url.host))
            )
        ):
            return normalize_url(str(external_url))

    # Fall back to the good old, deprecated `base_url`, with sanity
    # This if statement can be removed after `base_url` is removed.
    if hass.config.api is not None and hass.config.api.base_url:
        base_url = yarl.URL(hass.config.api.base_url)
        if (
            (
                not is_ip_address(str(base_url.host))
                or (
                    is_ip_address(str(base_url.host))
                    and not is_loopback(ip_address(base_url.host))
                )
            )
            and (
                not require_ssl
                or (
                    base_url.scheme == "https" and not is_ip_address(str(base_url.host))
                )
            )
            and (not require_standard_port or base_url.is_default_port())
            and (
                allow_local
                or not is_ip_address(str(base_url.host))
                or (
                    is_ip_address(str(base_url.host))
                    and not is_local(ip_address(base_url.host))
                )
            )
        ):
            return normalize_url(str(base_url))

    # Fallback to cloud as the last resort
    if "cloud" in hass.config.components:
        try:
            return cast(str, hass.components.cloud.async_remote_ui_url())
        except hass.components.cloud.CloudNotAvailable:
            pass

    # Fallback to the good old, deprecated `base_url`,
    # without sanity, for full backward compatibility
    # This if statement can be removed after `base_url` is removed.
    if hass.config.api is not None and hass.config.api.base_url:
        return normalize_url(str(base_url))

    # We have to be honest now, we have no viable option available
    raise NoURLAvailableError


@bind_hass
@callback
def async_get_external_url(hass: HomeAssistant) -> Optional[str]:
    """Get external url of this instance.

    Note: currently it takes 30 seconds after Home Assistant starts for
    cloud.async_remote_ui_url to work.
    """
    if "cloud" in hass.config.components:
        try:
            return cast(str, hass.components.cloud.async_remote_ui_url())
        except hass.components.cloud.CloudNotAvailable:
            pass

    if hass.config.api is None:
        return None

    base_url = yarl.URL(hass.config.api.base_url)

    try:
        if is_local(ip_address(base_url.host)):
            return None
    except ValueError:
        # ip_address raises ValueError if host is not an IP address
        pass

    return str(base_url)
