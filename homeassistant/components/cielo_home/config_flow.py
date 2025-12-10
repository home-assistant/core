"""Config Flow for Cielo integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER, TIMEOUT, NoDevicesError, NoUsernameError

DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
    }
)


class CieloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cielo integration."""

    VERSION = 1
    REAUTH_VERSION = 1

    entry: config_entries.ConfigEntry | None

    def __init__(self) -> None:
        """Initialize the flow."""
        self.client: CieloClient | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY].strip()

            # Check if an entry with this API key already exists.
            self._async_abort_entries_match({CONF_API_KEY: api_key})

            # Initialize client if not already done
            if self.client is None:
                self.client = CieloClient(
                    api_key="",
                    timeout=TIMEOUT,
                    session=async_get_clientsession(self.hass),
                )

            self.client.api_key = api_key

            try:
                # Attempt to get or refresh token to validate the key
                token = await self.client.get_or_refresh_token()

                # Validation successful. Prepare data for entry.
                user_input[CONF_API_KEY] = api_key
                user_input["token"] = token

            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except NoDevicesError:
                errors["base"] = "no_devices"
            except NoUsernameError:
                errors["base"] = "no_username"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception during config flow validation")
                errors["base"] = "unknown"
            else:
                # Set the unique ID using the validated token
                await self.async_set_unique_id(token)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Cielo Home ({api_key[:4]}*****************{api_key[-4:]})",
                    data=user_input,
                )

        # Show the user form
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "url": "https://www.home-assistant.io/integrations/cielo_home"
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of reauthentication flow upon API error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id") or ""
        )

        if self._reauth_entry:
            self.context["title_placeholders"] = {"name": self._reauth_entry.title}

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication with a NEW API key from the user."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "url": "https://www.home-assistant.io/integrations/cielo_home"
                },
            )

        api_key = user_input[CONF_API_KEY].strip()

        # Re-initialize client with the new key
        if self.client is None:
            self.client = CieloClient(
                api_key=api_key,
                timeout=TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
        else:
            self.client.api_key = api_key

        try:
            token = await self.client.get_or_refresh_token()
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except NoDevicesError:
            errors["base"] = "no_devices"
        except NoUsernameError:
            errors["base"] = "no_username"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during reauth validation")
            errors["base"] = "unknown"
        else:
            new_data = {
                **self._reauth_entry.data,
                CONF_API_KEY: api_key,
                "token": token,
            }

            self.hass.config_entries.async_update_entry(
                self._reauth_entry, unique_id=token
            )

            # Update the entry, and reload the integration
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data=new_data,
                reason="reauth_successful",
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "url": "https://www.home-assistant.io/integrations/cielo_home"
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
