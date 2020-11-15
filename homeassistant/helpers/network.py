"""Network helpers."""
from ipaddress import ip_address
from typing import Optional, cast

import yarl

from homeassistant.components.http import current_request
from homeassistant.core import HomeAssistant
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
def is_internal_request(hass: HomeAssistant) -> bool:
    """Test if the current request is internal."""
    try:
        _get_internal_url(hass, require_current_request=True)
        return True
    except NoURLAvailableError:
        return False


@bind_hass
def get_url(
    hass: HomeAssistant,
    *,
    require_current_request: bool = False,
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
    if require_current_request and current_request.get() is None:
        raise NoURLAvailableError

    order = [TYPE_URL_INTERNAL, TYPE_URL_EXTERNAL]
    if prefer_external:
        order.reverse()

    # Try finding an URL in the order specified
    for url_type in order:

        if allow_internal and url_type == TYPE_URL_INTERNAL:
            try:
                return _get_internal_url(
                    hass,
                    allow_ip=allow_ip,
                    require_current_request=require_current_request,
                    require_ssl=require_ssl,
                    require_standard_port=require_standard_port,
                )
            except NoURLAvailableError:
                pass

        if allow_external and url_type == TYPE_URL_EXTERNAL:
            try:
                return _get_external_url(
                    hass,
                    allow_cloud=allow_cloud,
                    allow_ip=allow_ip,
                    prefer_cloud=prefer_cloud,
                    require_current_request=require_current_request,
                    require_ssl=require_ssl,
                    require_standard_port=require_standard_port,
                )
            except NoURLAvailableError:
                pass

    # For current request, we accept loopback interfaces (e.g., 127.0.0.1),
    # the Supervisor hostname and localhost transparently
    request_host = _get_request_host()
    if (
        require_current_request
        and request_host is not None
        and hass.config.api is not None
    ):
        scheme = "https" if hass.config.api.use_ssl else "http"
        current_url = yarl.URL.build(
            scheme=scheme, host=request_host, port=hass.config.api.port
        )

        known_hostnames = ["localhost"]
        if hass.components.hassio.is_hassio():
            host_info = hass.components.hassio.get_host_info()
            known_hostnames.extend(
                [host_info["hostname"], f"{host_info['hostname']}.local"]
            )

        if (
            (
                (
                    allow_ip
                    and is_ip_address(request_host)
                    and is_loopback(ip_address(request_host))
                )
                or request_host in known_hostnames
            )
            and (not require_ssl or current_url.scheme == "https")
            and (not require_standard_port or current_url.is_default_port())
        ):
            return normalize_url(str(current_url))

    # We have to be honest now, we have no viable option available
    raise NoURLAvailableError


def _get_request_host() -> Optional[str]:
    """Get the host address of the current request."""
    request = current_request.get()
    if request is None:
        raise NoURLAvailableError
    return yarl.URL(request.url).host


@bind_hass
def _get_internal_url(
    hass: HomeAssistant,
    *,
    allow_ip: bool = True,
    require_current_request: bool = False,
    require_ssl: bool = False,
    require_standard_port: bool = False,
) -> str:
    """Get internal URL of this instance."""
    if hass.config.internal_url:
        internal_url = yarl.URL(hass.config.internal_url)
        if (
            (not require_current_request or internal_url.host == _get_request_host())
            and (not require_ssl or internal_url.scheme == "https")
            and (not require_standard_port or internal_url.is_default_port())
            and (allow_ip or not is_ip_address(str(internal_url.host)))
        ):
            return normalize_url(str(internal_url))

    # Fallback to old base_url
    try:
        return _get_deprecated_base_url(
            hass,
            internal=True,
            allow_ip=allow_ip,
            require_current_request=require_current_request,
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
        if (
            not is_loopback(ip_address(ip_url.host))
            and (not require_current_request or ip_url.host == _get_request_host())
            and (not require_standard_port or ip_url.is_default_port())
        ):
            return normalize_url(str(ip_url))

    raise NoURLAvailableError


@bind_hass
def _get_external_url(
    hass: HomeAssistant,
    *,
    allow_cloud: bool = True,
    allow_ip: bool = True,
    prefer_cloud: bool = False,
    require_current_request: bool = False,
    require_ssl: bool = False,
    require_standard_port: bool = False,
) -> str:
    """Get external URL of this instance."""
    if prefer_cloud and allow_cloud:
        try:
            return _get_cloud_url(hass)
        except NoURLAvailableError:
            pass

    if hass.config.external_url:
        external_url = yarl.URL(hass.config.external_url)
        if (
            (allow_ip or not is_ip_address(str(external_url.host)))
            and (
                not require_current_request or external_url.host == _get_request_host()
            )
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
        return _get_deprecated_base_url(
            hass,
            allow_ip=allow_ip,
            require_current_request=require_current_request,
            require_ssl=require_ssl,
            require_standard_port=require_standard_port,
        )
    except NoURLAvailableError:
        pass

    if allow_cloud:
        try:
            return _get_cloud_url(hass, require_current_request=require_current_request)
        except NoURLAvailableError:
            pass

    raise NoURLAvailableError


@bind_hass
def _get_cloud_url(hass: HomeAssistant, require_current_request: bool = False) -> str:
    """Get external Home Assistant Cloud URL of this instance."""
    if "cloud" in hass.config.components:
        try:
            cloud_url = yarl.URL(cast(str, hass.components.cloud.async_remote_ui_url()))
        except hass.components.cloud.CloudNotAvailable as err:
            raise NoURLAvailableError from err

        if not require_current_request or cloud_url.host == _get_request_host():
            return normalize_url(str(cloud_url))

    raise NoURLAvailableError


@bind_hass
def _get_deprecated_base_url(
    hass: HomeAssistant,
    *,
    internal: bool = False,
    allow_ip: bool = True,
    require_current_request: bool = False,
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
        and (not require_current_request or base_url.host == _get_request_host())
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
