"""Config flow to configure the Fumis integration."""

from __future__ import annotations

from collections.abc import Mapping
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].replace(":", "").replace("-", "").upper()
            fumis = Fumis(
                mac=mac,
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
                await self.async_set_unique_id(format_mac(mac), raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.controller.model_name or "Fumis",
                    data={
                        CONF_MAC: mac,
                        CONF_PIN: user_input[CONF_PIN],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_MAC): TextSelector(
                            TextSelectorConfig(autocomplete="off")
                        ),
                        vol.Required(CONF_PIN): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication of a Fumis stove."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            fumis = Fumis(
                mac=reauth_entry.data[CONF_MAC],
                password=user_input[CONF_PIN],
                session=async_get_clientsession(self.hass),
            )
            try:
                await fumis.update_info()
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
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PIN: user_input[CONF_PIN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )
