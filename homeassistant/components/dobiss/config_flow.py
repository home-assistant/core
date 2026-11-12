"""Configure Dobiss NXT through the user interface."""

from typing import Any, override

from dobiss_nxt import (
    DobissAuthenticationError,
    DobissClient,
    DobissError,
    normalize_host,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_SECRET, DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(probatio.Secret(CONF_API_SECRET)): str,
        probatio.Optional(CONF_SSL, default=False): bool,
    }
)


class DobissConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Dobiss NXT setup."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate host and credentials before saving the configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                if not user_input[CONF_API_SECRET]:
                    errors["base"] = "invalid_auth"
                else:
                    client = DobissClient(
                        async_get_clientsession(self.hass),
                        host,
                        user_input[CONF_API_SECRET],
                        secure=user_input[CONF_SSL],
                    )
                    try:
                        lights = await client.discover_lights()
                        await client.light_states(lights)
                    except DobissAuthenticationError:
                        errors["base"] = "invalid_auth"
                    except DobissError:
                        errors["base"] = "cannot_connect"
                    else:
                        self._async_abort_entries_match({CONF_HOST: host})
                        return self.async_create_entry(
                            title=f"Dobiss ({host})",
                            data=user_input | {CONF_HOST: host},
                        )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
