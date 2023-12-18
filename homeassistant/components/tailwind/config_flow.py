"""Config flow to configure the Tailwind integration."""
from __future__ import annotations

from typing import Any

from gotailwind import (
    Tailwind,
    TailwindAuthenticationError,
    TailwindConnectionError,
    TailwindUnsupportedFirmwareVersionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class TailwindFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Tailwind config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            tailwind = Tailwind(
                host=user_input[CONF_HOST],
                token=user_input[CONF_TOKEN],
                session=async_get_clientsession(self.hass),
            )
            try:
                status = await tailwind.status()
            except TailwindUnsupportedFirmwareVersionError:
                return self.async_abort(reason="unsupported_firmware")
            except TailwindAuthenticationError:
                errors[CONF_TOKEN] = "invalid_auth"
            except TailwindConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Tailwind {status.product}",
                    data=user_input,
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                    vol.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={
                "url": "https://web.gotailwind.com/client/integration/local-control-key",
            },
            errors=errors,
        )
