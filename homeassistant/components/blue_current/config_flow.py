"""Config flow for Blue Current integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    AlreadyConnected,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


class BlueCurrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Blue Current."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            client = Client()
            api_token = user_input[CONF_API_TOKEN]

            try:
                customer_id = await client.validate_api_token(api_token)
                email = await client.get_email()
            except WebsocketError:
                errors["base"] = "cannot_connect"
            except RequestLimitReached:
                errors["base"] = "limit_reached"
            except AlreadyConnected:
                errors["base"] = "already_connected"
            except InvalidApiToken:
                errors["base"] = "invalid_token"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                if self.source != SOURCE_REAUTH:
                    await self.async_set_unique_id(customer_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=email, data=user_input)

                reauth_entry = self._get_reauth_entry()
                if reauth_entry.unique_id == customer_id:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=user_input
                    )

                return self.async_abort(
                    reason="wrong_account",
                    description_placeholders={"email": email},
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()
