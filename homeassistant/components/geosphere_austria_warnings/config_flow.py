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
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_ZONE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE, default="zone.home"): EntitySelector(
            EntitySelectorConfig(domain="zone")
        )
    }
)


class GeoSphereConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GeoSphere Austria Warnings."""

    VERSION = 1

    async def _async_validate_zone(
        self, zone_entity_id: str, errors: dict[str, str]
    ) -> tuple[Municipality, dict[str, float]] | None:
        """Resolve the zone to a municipality via the API."""
        if (zone := self.hass.states.get(zone_entity_id)) is None:
            errors["base"] = "zone_not_found"
            return None
        latitude: float = zone.attributes[ATTR_LATITUDE]
        longitude: float = zone.attributes[ATTR_LONGITUDE]
        client = GeoSphereWarningsClient(async_get_clientsession(self.hass))
        try:
            location_warnings = await client.get_warnings_for_coords(
                latitude, longitude
            )
        except GeoSphereMunicipalityNotFoundError:
            errors["base"] = "municipality_not_found"
        except GeoSphereWarningsError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return location_warnings.municipality, {
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
            }
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            result := await self._async_validate_zone(user_input[CONF_ZONE], errors)
        ):
            municipality, data = result
            await self.async_set_unique_id(municipality.municipality_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=municipality.name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the selected zone."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            result := await self._async_validate_zone(user_input[CONF_ZONE], errors)
        ):
            municipality, data = result
            await self.async_set_unique_id(municipality.municipality_id)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title=municipality.name,
                data=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
