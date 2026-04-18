"""Config flow for IntelliClima integration."""

from typing import Any

from pyintelliclima import IntelliClimaAPI, IntelliClimaAPIError, IntelliClimaAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class IntelliClimaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliClima VMC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            # Validate credentials
            session = async_get_clientsession(self.hass)
            api = IntelliClimaAPI(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                # Test authentication
                await api.authenticate()

                # Get devices to ensure we can communicate with API
                devices = await api.get_all_device_status()

            except IntelliClimaAuthError:
                errors["base"] = "invalid_auth"
            except IntelliClimaAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if devices.num_devices == 0:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"IntelliClima ({user_input[CONF_USERNAME]})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
