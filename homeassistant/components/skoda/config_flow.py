"""Config flow for the Škoda integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiTimeoutError,
    OpenApiVehicleNotFoundError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.vehicle import VehicleResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_VIN, DOMAIN, MYSKODA_URL

_LOGGER = logging.getLogger(__name__)

# Form for initial user input: VIN and API key.
STEP_VEHICLE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VIN): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class SkodaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Škoda."""

    VERSION = 1

    async def _test_credentials(self, vin: str, api_key: str) -> VehicleResponse:
        """Validate credentials and VIN by requesting the vehicle status from OpenAPI."""
        session = async_get_clientsession(self.hass)
        client = OpenAPIClient(api_key=api_key, session=session)
        # calling an endpoint /api/v1/vehicle/{vin}
        return await client.get_vehicle(vin)

    async def _async_validate(
        self, vin: str, api_key: str
    ) -> tuple[VehicleResponse | None, str | None]:
        """Validate credentials, returning (response, None) or (None, error_code)."""
        try:
            return await self._test_credentials(vin, api_key), None
        except OpenApiTimeoutError:
            return None, "timeout_connect"
        except OpenApiAuthenticationError:
            return None, "invalid_auth"
        except OpenApiForbiddenError:
            return None, "access_forbidden"
        except OpenApiVehicleNotFoundError:
            return None, "vehicle_not_found"
        except OpenApiRateLimitError:
            return None, "rate_limit_exceeded"
        except OpenApiServerError:
            return None, "cannot_connect"
        except OpenApiError:
            return None, "api_error"
        except Exception:
            _LOGGER.exception("Unexpected error during vehicle verification")
            return None, "unknown"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where user provides VIN and API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            api_key = user_input[CONF_API_KEY].strip()

            # Basic format validation for the VIN
            if len(vin) != 17:
                errors[CONF_VIN] = "invalid_vin_length"
            else:
                # Setting a unique ID for the config entry based on the VIN to prevent duplicates.
                await self.async_set_unique_id(vin)
                self._abort_if_unique_id_configured()

                vehicle_response, error = await self._async_validate(vin, api_key)
                if error:
                    errors["base"] = error
                else:
                    # Try to get a vehicle model name as an entry title, fallback to VIN if not available.
                    title = f"Škoda {vin}"
                    if (
                        vehicle_response
                        and vehicle_response.vehicle
                        and vehicle_response.vehicle.name
                    ):
                        title = f"Škoda {vehicle_response.vehicle.name}"

                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_VIN: vin,
                            CONF_API_KEY: api_key,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_VEHICLE_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_url": f"[{MYSKODA_URL}]({MYSKODA_URL})",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored API key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a new API key and validate it before saving."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            vin = reauth_entry.data[CONF_VIN]

            _, error = await self._async_validate(vin, api_key)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
