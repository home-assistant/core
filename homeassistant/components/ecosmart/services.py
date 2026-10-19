"""Service actions for the ecosmart integration."""

from typing import Final

from aioecosmart import (
    EcosmartAuthError,
    EcosmartError,
    EcosmartRateLimitError,
    Forecast,
)
import probatio

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util.json import JsonValueType

from .const import DOMAIN, FORECAST_HOURS
from .coordinator import EcosmartConfigEntry, EcosmartCoordinator, retry_delay

SERVICE_GET_FORECASTS: Final = "get_forecasts"
ATTR_ICP: Final = "icp"

GET_FORECASTS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Optional(ATTR_ICP): cv.string,
    }
)


def _grid_exit_point(coordinator: EcosmartCoordinator, icp: str | None) -> str:
    """Return the grid exit point whose forecast the caller asked for.

    Prices are published per grid exit point, so the ICP only has to be named
    when the key reaches connection points behind more than one.
    """
    scopes = coordinator.identity.allowed_icps
    if not scopes:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_icps"
        )
    icps = ", ".join(scope.icp for scope in scopes)
    if icp is not None:
        for scope in scopes:
            if scope.icp == icp:
                return scope.poc
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="icp_not_found",
            translation_placeholders={"icp": icp, "icps": icps},
        )
    if len(coordinator.pocs) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="icp_required",
            translation_placeholders={"icps": icps},
        )
    return coordinator.pocs[0]


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
    """Fetch the wholesale price forecast for one grid exit point.

    The request is made on demand rather than polled, so the spot price
    sensor's request budget is untouched until someone asks.
    """
    entry: EcosmartConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    coordinator = entry.runtime_data
    poc = _grid_exit_point(coordinator, call.data.get(ATTR_ICP))
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
        SERVICE_GET_FORECASTS,
        _async_get_forecasts,
        schema=GET_FORECASTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
