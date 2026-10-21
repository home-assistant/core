"""Service actions for the ecosmart integration."""

from enum import StrEnum

from aioecosmart import (
    EcosmartAuthError,
    EcosmartError,
    EcosmartRateLimitError,
    Forecast,
)
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import service
from homeassistant.helpers.selector import DeviceSelector
from homeassistant.util.json import JsonValueType

from .const import DOMAIN, FORECAST_HOURS
from .coordinator import EcosmartConfigEntry, EcosmartCoordinator, retry_delay


class EcosmartService(StrEnum):
    """Store keys for ecosmart services."""

    GET_FORECASTS = "get_forecasts"


GET_FORECASTS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): DeviceSelector(
            {"filter": [{"integration": DOMAIN}]}
        ),
    }
)


def _coordinator_and_grid_exit_point(
    hass: HomeAssistant, device_id: str
) -> tuple[EcosmartCoordinator, str]:
    """Return the coordinator and grid exit point behind a connection point device.

    Each ICP has its own device, so the caller names exactly one connection
    point and nothing is chosen on their behalf.
    """
    entry: EcosmartConfigEntry
    device, entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, device_id, include_child_devices=False
    )
    icp = next(
        (value for domain, value in device.identifiers if domain == DOMAIN), None
    )
    if icp is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": device_id},
        )
    coordinator = entry.runtime_data
    for scope in coordinator.identity.allowed_icps:
        if scope.icp == icp:
            return coordinator, scope.poc
    # The device outlived the key's access to its ICP.
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="icp_not_on_key",
        translation_placeholders={"icp": icp},
    )


def _serialize(forecast: Forecast) -> ServiceResponse:
    """Return the forecast as a service response, prices in c/kWh."""
    points: list[JsonValueType] = [
        {
            "start_time": point.starts_at.isoformat(),
            "price": point.price_cents_per_kwh_incl_gst,
            "price_excl_gst": point.price_cents_per_kwh,
        }
        for point in forecast.points
    ]
    return {"forecasts": points}


async def _async_get_forecasts(call: ServiceCall) -> ServiceResponse:
    """Fetch the wholesale price forecast for one connection point.

    The request is made on demand rather than polled, so the spot price
    sensor's request budget is untouched until someone asks.
    """
    coordinator, poc = _coordinator_and_grid_exit_point(
        call.hass, call.data[ATTR_DEVICE_ID]
    )
    try:
        forecast = await coordinator.client.forecast(poc, FORECAST_HOURS)
    except EcosmartAuthError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except EcosmartRateLimitError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="forecast_rate_limited",
            translation_placeholders={"retry_after": str(retry_delay(err))},
        ) from err
    except EcosmartError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    return _serialize(forecast)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ecosmart service actions."""
    hass.services.async_register(
        DOMAIN,
        EcosmartService.GET_FORECASTS,
        _async_get_forecasts,
        schema=GET_FORECASTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
