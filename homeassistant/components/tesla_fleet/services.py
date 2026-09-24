"""Services for the Tesla Fleet integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

NAVIGATION_GPS_REQUEST_SCHEMA = probatio.Schema(
    {
        probatio.Required("device_id"): cv.string,
        probatio.Required("latitude"): probatio.All(
            probatio.Coerce(float), probatio.Range(min=-90, max=90)
        ),
        probatio.Required("longitude"): probatio.All(
            probatio.Coerce(float), probatio.Range(min=-180, max=180)
        ),
        probatio.Optional("order"): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0)
        ),
    }
)


async def async_handle_navigation_gps_request(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle the navigation_gps_request service call."""
    device_id: str = call.data["device_id"]
    latitude: float = call.data["latitude"]
    longitude: float = call.data["longitude"]
    order: int | None = call.data.get("order")

    # 1. Resolve target device entry from registry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    # 2. Extract VIN from device identifiers
    vin: str | None = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:
            vin = identifier[1]
            break

    if vin is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_no_vin",
            translation_placeholders={"device_id": device_id},
        )

    # 3. Obtain API instance from hass.data using device config entry
    api = None
    for entry_id in device_entry.config_entries:
        if (
            entry := hass.config_entries.async_get_entry(entry_id)
        ) and entry.domain == DOMAIN:
            api = getattr(entry.runtime_data, "api", entry.runtime_data)
            break

    if api is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="instance_not_found",
            translation_placeholders={"device_id": device_id},
        )

    # 4. Dispatch call to Tesla Fleet API client
    try:
        await api.navigation_gps_request(
            vin=vin,
            lat=latitude,
            lon=longitude,
            order=order,
        )
    except Exception as err:
        raise HomeAssistantError(
            f"Failed to send navigation request to vehicle {vin}: {err}"
        ) from err


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Tesla Fleet integration services."""

    async def _handle_navigation_gps_request(call: ServiceCall) -> None:
        await async_handle_navigation_gps_request(hass, call)

    hass.services.async_register(
        domain=DOMAIN,
        service="navigation_gps_request",
        service_func=_handle_navigation_gps_request,
        schema=NAVIGATION_GPS_REQUEST_SCHEMA,
    )
