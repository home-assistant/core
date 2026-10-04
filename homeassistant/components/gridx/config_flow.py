"""Config flow for the gridX integration."""

from typing import Any, override

from gridx_connector import GridXAuthenticationError, GridXError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, LOGGER
from .coordinator import create_connector

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


class GridxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gridX."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]
            connector = create_connector(self.hass, username, password)
            try:
                await connector.initialize()
            except GridXAuthenticationError:
                errors["base"] = "invalid_auth"
            except GridXError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not connector.systems:
                    errors["base"] = "no_systems"
                else:
                    await self.async_set_unique_id(username.lower())
                    self._abort_if_unique_id_configured(
                        updates={CONF_PASSWORD: password}
                    )
                    return self.async_create_entry(
                        title=username,
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
