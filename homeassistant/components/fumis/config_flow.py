"""Config flow to configure the Fumis integration."""

from __future__ import annotations

from typing import Any

from fumis import (
    Fumis,
    FumisAuthenticationError,
    FumisConnectionError,
    FumisStoveOfflineError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class FumisFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Fumis config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            fumis = Fumis(
                mac=user_input[CONF_MAC],
                password=user_input[CONF_PIN],
                session=async_get_clientsession(self.hass),
            )
            try:
                info = await fumis.update_info()
            except FumisAuthenticationError:
                errors[CONF_PIN] = "invalid_auth"
            except FumisStoveOfflineError:
                errors["base"] = "device_offline"
            except FumisConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    format_mac(user_input[CONF_MAC]), raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.controller.model_name or "Fumis",
                    data=user_input,
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MAC, default=user_input.get(CONF_MAC)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                    vol.Required(CONF_PIN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )
