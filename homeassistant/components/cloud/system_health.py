"""Provide info to system health."""

from typing import Any

from hass_nabucasa import Cloud

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .client import CloudClient
from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/config/cloud")


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]
    client = cloud.client

    data: dict[str, Any] = {
        "logged_in": cloud.is_logged_in,
    }

    if cloud.is_logged_in:
        data["subscription_expiration"] = cloud.expiration_date
        data["relayer_connected"] = cloud.is_connected
        data["relayer_region"] = client.relayer_region
        data["remote_enabled"] = client.prefs.remote_enabled
        data["remote_connected"] = cloud.remote.is_connected
        data["alexa_enabled"] = client.prefs.alexa_enabled
        data["google_enabled"] = client.prefs.google_enabled
        data["remote_server"] = cloud.remote.snitun_server
        data["certificate_status"] = cloud.remote.certificate_status
        data["instance_id"] = client.prefs.instance_id

    data["can_reach_cert_server"] = system_health.async_check_can_reach_url(
        hass, f"https://{cloud.acme_server}/directory"
    )
    data["can_reach_cloud_auth"] = system_health.async_check_can_reach_url(
        hass,
        f"https://cognito-idp.{cloud.region}.amazonaws.com/{cloud.user_pool_id}/.well-known/jwks.json",
    )
    data["can_reach_cloud"] = system_health.async_check_can_reach_url(
        hass, f"https://{cloud.relayer_server}/status"
    )

    return data
