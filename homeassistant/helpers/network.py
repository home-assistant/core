"""Network helpers."""
from ipaddress import ip_address
from typing import Optional, cast

import yarl

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.network import is_local


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
