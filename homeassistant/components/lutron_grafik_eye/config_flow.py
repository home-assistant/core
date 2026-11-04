"""Config flow for the Lutron GRAFIK Eye integration."""

import logging
from typing import Any, override

from grafikeye import GrafikEyeController
from grafikeye.exceptions import (
    GrafikEyeAuthenticationError,
    GrafikEyeConnectionError,
    GrafikEyeConnectionInUseError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

LOGGER = logging.getLogger(__name__)


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

            controller = GrafikEyeController(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                login=user_input[CONF_PASSWORD],
            )

            try:
                await controller.connect()
            except GrafikEyeAuthenticationError:
                errors["base"] = "invalid_auth"
            except GrafikEyeConnectionInUseError:
                errors["base"] = "connection_in_use"
            except GrafikEyeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception(
                    "Unexpected exception connecting to GRAFIK Eye Ethernet interface"
                )
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"GRAFIK Eye ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            finally:
                await controller.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST,
                        default=user_input.get(CONF_HOST, "") if user_input else "",
                    ): str,
                    probatio.Required(
                        CONF_PORT,
                        default=user_input.get(CONF_PORT, DEFAULT_PORT)
                        if user_input
                        else DEFAULT_PORT,
                    ): int,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )
