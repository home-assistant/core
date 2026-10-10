"""Diagnostics support for Daikin Onecta."""

from typing import Any

from aiohttp import ClientError
from daikin_onecta.exceptions import OnectaError
from daikin_onecta.models import Site

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import DaikinOnectaConfigEntry

TO_REDACT = {
    "access_token",
    "countryCode",
    "country_code",
    "embeddedId",
    "embedded_id",
    "entry_id",
    "gatewayDevices",
    "gateway_device_id",
    "gateway_device_ids",
    "id",
    "ipAddress",
    "latitude",
    "longitude",
    "macAddress",
    "mac_address",
    "name",
    "placeID",
    "place_id",
    "refresh_token",
    "serialNumber",
    "serial_number",
    "sgtin",
    "ssid",
    "token",
    "unique_id",
    "users",
    "wifiConnectionSSID",
}


def _site_membership(sites: list[Site], gateway_device_id: str) -> bool | None:
    """Return a gateway's membership across complete site responses."""
    membership = [site.has_gateway_device(gateway_device_id) for site in sites]
    if True in membership:
        return True
    return None if None in membership else False


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: DaikinOnectaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics and make one explicit Sites API lookup."""
    coordinator = entry.runtime_data
    try:
        sites = await coordinator.api.get_sites()
    except (OnectaError, ClientError, TimeoutError) as err:
        site_diagnostics: dict[str, Any] = {
            "error": {
                "type": type(err).__name__,
                "status": getattr(err, "status", None),
            }
        }
    else:
        site_diagnostics = {
            "data": [site.to_dict() for site in sites],
            "gateway_membership": [
                {
                    "gateway_device_id": device.id,
                    "linked_to_site": _site_membership(sites, device.id),
                }
                for device in (coordinator.data or {}).values()
            ],
        }

    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "rate_limits": coordinator.api.rate_limits,
            },
            "sites": site_diagnostics,
            "devices": [
                device.device.to_dict() for device in (coordinator.data or {}).values()
            ],
        },
        TO_REDACT,
    )
