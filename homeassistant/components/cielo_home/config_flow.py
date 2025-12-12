"""Config Flow for Cielo integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
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

    async def _async_validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate the API key, initialize the client, and return errors or token."""
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
            return {"base": "invalid_auth"}
        except ConnectionError:
            return {"base": "cannot_connect"}
        except NoDevicesError:
            return {"base": "no_devices"}
        except NoUsernameError:
            return {"base": "no_username"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during config flow validation")
            return {"base": "unknown"}

        return {"token": token}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY].strip()

            self._async_abort_entries_match({CONF_API_KEY: api_key})

            validation_result = await self._async_validate_api_key(api_key)

            if "base" in validation_result:
                errors = validation_result
            else:
                token: str = validation_result[CONF_TOKEN]

                user_input[CONF_API_KEY] = api_key
                user_input[CONF_TOKEN] = token

                await self.async_set_unique_id(token)
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

        if self._reauth_entry and self._reauth_entry.unique_id:
            await self.async_set_unique_id(self._reauth_entry.unique_id)

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

        validation_result = await self._async_validate_api_key(api_key)

        if "base" in validation_result:
            errors = validation_result
        else:
            token: str = validation_result[CONF_TOKEN]

            new_data = {
                **self._reauth_entry.data,
                CONF_API_KEY: api_key,
                CONF_TOKEN: token,
            }

            self.hass.config_entries.async_update_entry(
                self._reauth_entry, unique_id=token, data=new_data
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
