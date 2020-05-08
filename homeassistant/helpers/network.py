"""Network helpers."""
from ipaddress import ip_address
from typing import cast

import yarl

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.util.network import (
    is_ip_address,
    is_local,
    is_loopback,
    is_private,
    normalize_url,
)

TYPE_URL_INTERNAL = "internal_url"
TYPE_URL_EXTERNAL = "external_url"


class NoURLAvailableError(HomeAssistantError):
    """An URL to the Home Assistant instance is not available."""


@bind_hass
@callback
def async_get_url(
    hass: HomeAssistant,
    *,
    require_ssl: bool = False,
    require_standard_port: bool = False,
    allow_internal: bool = True,
    allow_external: bool = True,
    allow_cloud: bool = True,
    allow_ip: bool = True,
    prefer_external: bool = False,
    prefer_cloud: bool = False,
) -> str:
    """Get a URL to this instance."""
    order = [TYPE_URL_INTERNAL, TYPE_URL_EXTERNAL]
    if prefer_external:
        order.reverse()

    # Try finding an URL in the order specified
    for url_type in order:

        if allow_internal and url_type == TYPE_URL_INTERNAL:
            try:
                return _async_get_internal_url(
                    hass,
                    allow_ip=allow_ip,
                    require_ssl=require_ssl,
                    require_standard_port=require_standard_port,
                )
            except NoURLAvailableError:
                pass

        if allow_external and url_type == TYPE_URL_EXTERNAL:
            try:
                return _async_get_external_url(
                    hass,
                    allow_cloud=allow_cloud,
                    allow_ip=allow_ip,
                    prefer_cloud=prefer_cloud,
                    require_ssl=require_ssl,
                    require_standard_port=require_standard_port,
                )
            except NoURLAvailableError:
                pass

    # We have to be honest now, we have no viable option available
    raise NoURLAvailableError


@bind_hass
@callback
def _async_get_internal_url(
    hass: HomeAssistant,
    *,
    allow_ip: bool = True,
    require_ssl: bool = False,
    require_standard_port: bool = False,
) -> str:
    """Get internal URL of this instance."""
    if hass.config.internal_url:
        internal_url = yarl.URL(hass.config.internal_url)
        if (
            (not require_ssl or internal_url.scheme == "https")
            and (not require_standard_port or internal_url.is_default_port())
            and (allow_ip or not is_ip_address(str(internal_url.host)))
        ):
            return normalize_url(str(internal_url))

    # Fallback to old base_url
    try:
        return _async_get_deprecated_base_url(
            hass,
            internal=True,
            allow_ip=allow_ip,
            require_ssl=require_ssl,
            require_standard_port=require_standard_port,
        )
    except NoURLAvailableError:
        pass

    # Fallback to detected local IP
    if allow_ip and not (
        require_ssl or hass.config.api is None or hass.config.api.use_ssl
    ):
        ip_url = yarl.URL.build(
            scheme="http", host=hass.config.api.local_ip, port=hass.config.api.port
        )
        if not is_loopback(ip_address(ip_url.host)) and (
            not require_standard_port or ip_url.is_default_port()
        ):
            return normalize_url(str(ip_url))

    raise NoURLAvailableError


@bind_hass
@callback
def _async_get_external_url(
    hass: HomeAssistant,
    *,
    allow_cloud: bool = True,
    allow_ip: bool = True,
    prefer_cloud: bool = False,
    require_ssl: bool = False,
    require_standard_port: bool = False,
) -> str:
    """Get external URL of this instance."""
    if prefer_cloud and allow_cloud:
        try:
            return _async_get_cloud_url(hass)
        except NoURLAvailableError:
            pass

    if hass.config.external_url:
        external_url = yarl.URL(hass.config.external_url)
        if (
            (allow_ip or not is_ip_address(str(external_url.host)))
            and (not require_standard_port or external_url.is_default_port())
            and (
                not require_ssl
                or (
                    external_url.scheme == "https"
                    and not is_ip_address(str(external_url.host))
                )
            )
        ):
            return normalize_url(str(external_url))

    try:
        return _async_get_deprecated_base_url(
            hass,
            allow_ip=allow_ip,
            require_ssl=require_ssl,
            require_standard_port=require_standard_port,
        )
    except NoURLAvailableError:
        pass

    if allow_cloud:
        try:
            return _async_get_cloud_url(hass)
        except NoURLAvailableError:
            pass

    raise NoURLAvailableError


@bind_hass
@callback
def _async_get_cloud_url(hass: HomeAssistant) -> str:
    """Get external Home Assistant Cloud URL of this instance."""
    if "cloud" in hass.config.components:
        try:
            return cast(str, hass.components.cloud.async_remote_ui_url())
        except hass.components.cloud.CloudNotAvailable:
            pass

    raise NoURLAvailableError


@bind_hass
@callback
def _async_get_deprecated_base_url(
    hass: HomeAssistant,
    *,
    internal: bool = False,
    allow_ip: bool = True,
    require_ssl: bool = False,
    require_standard_port: bool = False,
) -> str:
    """Work with the deprecated `base_url`, used as fallback."""
    if hass.config.api is None or not hass.config.api.deprecated_base_url:
        raise NoURLAvailableError

    base_url = yarl.URL(hass.config.api.deprecated_base_url)
    # Rules that apply to both internal and external
    if (
        (allow_ip or not is_ip_address(str(base_url.host)))
        and (not require_ssl or base_url.scheme == "https")
        and (not require_standard_port or base_url.is_default_port())
    ):
        # Check to ensure an internal URL
        if internal and (
            str(base_url.host).endswith(".local")
            or (
                is_ip_address(str(base_url.host))
                and not is_loopback(ip_address(base_url.host))
                and is_private(ip_address(base_url.host))
            )
        ):
            return normalize_url(str(base_url))

        # Check to ensure an external URL (a little)
        if (
            not internal
            and not str(base_url.host).endswith(".local")
            and not (
                is_ip_address(str(base_url.host))
                and is_local(ip_address(str(base_url.host)))
            )
        ):
            return normalize_url(str(base_url))

    raise NoURLAvailableError
