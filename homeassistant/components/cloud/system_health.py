"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DATA_CLOUD


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/config/cloud")


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    cloud = hass.data[DATA_CLOUD]
    client = cloud.client

    data: dict[str, Any] = {
        "logged_in": cloud.is_logged_in,
    }

    if cloud.is_logged_in:
        data["subscription_expiration"] = cloud.expiration_date
        data["valid_subscription"] = cloud.valid_subscription
        data["relayer_connected"] = cloud.is_connected
        data["relayer_region"] = client.relayer_region
        data["remote_enabled"] = client.prefs.remote_enabled
        data["remote_connected"] = cloud.remote.is_connected
        data["remote_server"] = cloud.remote.snitun_server
        data["remote_instance_domain"] = cloud.remote.instance_domain
        data["remote_alias"] = cloud.remote.alias
        data["alexa_enabled"] = client.prefs.alexa_enabled
        data["google_enabled"] = client.prefs.google_enabled
        data["cloud_ice_servers_enabled"] = client.prefs.cloud_ice_servers_enabled
        data["certificate_status"] = cloud.remote.certificate_status
        data["instance_id"] = client.prefs.instance_id
        data["iot_state"] = cloud.iot.state
        data["iot_tries"] = cloud.iot.tries
        data["cloudhooks_count"] = len(client.cloudhooks)

        if (cert := cloud.remote.certificate) is not None:
            data["certificate_expire_date"] = cert.expire_date
            data["certificate_fingerprint"] = cert.fingerprint
            if cert.alternative_names:
                data["certificate_alternative_names"] = cert.alternative_names

        if (disconnect := cloud.iot.last_disconnect_reason) is not None:
            data["iot_last_disconnect_clean"] = disconnect.clean
            data["iot_last_disconnect_reason"] = disconnect.reason

        remote_latency_avg_by_location: dict[str, float | None] = {}
        for location, result in cloud.remote.latency_by_location.items():
            remote_latency_avg_by_location[location] = result["avg"]

        if remote_latency_avg_by_location:
            data["remote_latency_avg_by_location"] = remote_latency_avg_by_location

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
