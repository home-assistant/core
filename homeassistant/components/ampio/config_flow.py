"""Config flow for the Ampio integration."""

import logging
from typing import Any, override

from ampio_mqtt import AccessTier, AmpioAuthError, AmpioClient, AmpioConnectionError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import ADMIN_USERNAME, DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class AmpioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ampio."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await AmpioClient.check_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except AmpioAuthError:
                errors["base"] = "invalid_auth"
            except AmpioConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Setup picks the client class by username, so the name must match the tier.
                if (info.access_tier is AccessTier.ADMIN) != (
                    user_input[CONF_USERNAME] == ADMIN_USERNAME
                ):
                    errors[CONF_USERNAME] = "admin_login_name"
                else:
                    await self.async_set_unique_id(info.server_key)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_HOST], data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {CONF_HOST: DEFAULT_HOST}
            ),
            errors=errors,
        )
