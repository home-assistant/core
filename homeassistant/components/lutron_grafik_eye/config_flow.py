"""Config flow for the Lutron GRAFIK Eye integration."""

import logging
from typing import Any, override

from grafikeye import (
    GrafikEyeAuthenticationError,
    GrafikEyeClient,
    GrafikEyeConnectionError,
    GrafikEyeConnectionInUseError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GrafikEyeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GRAFIK Eye."""

    VERSION = 1

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            client = GrafikEyeClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                login=user_input[CONF_PASSWORD],
            )

            try:
                await client.connect()
            except GrafikEyeAuthenticationError:
                errors["base"] = "invalid_auth"
            except GrafikEyeConnectionInUseError:
                errors["base"] = "connection_in_use"
            except GrafikEyeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception connecting to GRAFIK Eye Ethernet interface"
                )
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"GRAFIK Eye ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): str,
                        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
                        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )
