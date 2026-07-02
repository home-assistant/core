"""Services for the Google Air Quality integration."""

from datetime import timedelta
from typing import Final, cast

from google_air_quality_api.exceptions import GoogleAirQualityApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, selector

from .const import DOMAIN
from .coordinator import GoogleAirQualityConfigEntry

ATTR_HOURS: Final = "hours"

FORECAST_HOURS_MAX: Final = 96

SERVICE_GET_FORECAST: Final = "get_forecast"

SERVICE_GET_FORECAST_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): selector.DeviceSelector({"integration": DOMAIN}),
        vol.Required(ATTR_HOURS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=FORECAST_HOURS_MAX)
        ),
    }
)


def _get_config_entry_and_subentry_id(
    hass: HomeAssistant, device_id: str
) -> tuple[GoogleAirQualityConfigEntry, str]:
    """Get the config entry and subentry from a selected location device."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id, subentry_ids in device.config_entries_subentries.items():
            config_entry: ConfigEntry | None = hass.config_entries.async_get_entry(
                entry_id
            )
            if config_entry is None or config_entry.domain != DOMAIN:
                continue

            gaq_config_entry = cast(GoogleAirQualityConfigEntry, config_entry)
            for subentry_id in subentry_ids:
                if (
                    subentry_id is not None
                    and subentry_id
                    in gaq_config_entry.runtime_data.subentries_runtime_data
                ):
                    return gaq_config_entry, subentry_id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
    )


async def _async_get_forecast(call: ServiceCall) -> ServiceResponse:
    """Fetch the air quality forecast for a configured location."""
    config_entry, subentry_id = _get_config_entry_and_subentry_id(
        call.hass, call.data[ATTR_DEVICE_ID]
    )

    coordinator = config_entry.runtime_data.subentries_runtime_data[subentry_id]

    try:
        forecast = await config_entry.runtime_data.api.async_get_forecast(
            coordinator.lat,
            coordinator.long,
            timedelta(hours=call.data[ATTR_HOURS]),
        )
    except GoogleAirQualityApiError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_fetch",
        ) from err

    return cast(
        ServiceResponse,
        {
            "forecast_time": forecast.hourly_forecasts[0].date_time,
            "indexes": forecast.hourly_forecasts[0].indexes,
            "pollutants": forecast.hourly_forecasts[0].pollutants,
        },
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FORECAST,
        _async_get_forecast,
        schema=SERVICE_GET_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
