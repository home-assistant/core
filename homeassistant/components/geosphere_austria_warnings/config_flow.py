"""Config flow for the GeoSphere Austria Warnings integration."""

from typing import Any

from pygeosphere_warnings import (
    GeoSphereMunicipalityNotFoundError,
    GeoSphereWarningsClient,
    GeoSphereWarningsError,
    Municipality,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN, LOGGER


def _build_schema(hass: HomeAssistant) -> vol.Schema:
    """Return the user step schema defaulting to the Home Assistant location."""
    return vol.Schema(
        {
            vol.Required(
                CONF_LOCATION,
                default={
                    CONF_LATITUDE: hass.config.latitude,
                    CONF_LONGITUDE: hass.config.longitude,
                },
            ): LocationSelector(LocationSelectorConfig(radius=False))
        }
    )


class GeoSphereConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GeoSphere Austria Warnings."""

    VERSION = 1

    async def _async_validate_location(
        self, location: dict[str, float], errors: dict[str, str]
    ) -> Municipality | None:
        """Resolve the location to a municipality via the API."""
        client = GeoSphereWarningsClient(async_get_clientsession(self.hass))
        try:
            location_warnings = await client.get_warnings_for_coords(
                location[CONF_LATITUDE], location[CONF_LONGITUDE]
            )
        except GeoSphereMunicipalityNotFoundError:
            errors["base"] = "municipality_not_found"
        except GeoSphereWarningsError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return location_warnings.municipality
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            if municipality := await self._async_validate_location(location, errors):
                await self.async_set_unique_id(municipality.municipality_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=municipality.name,
                    data={
                        CONF_LATITUDE: location[CONF_LATITUDE],
                        CONF_LONGITUDE: location[CONF_LONGITUDE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass),
            errors=errors,
        )
