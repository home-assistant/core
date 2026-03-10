"""Config Flow for Cielo integration."""

from __future__ import annotations

from typing import Any, Final

from aiohttp import ClientError
from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError, CieloError
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

from .const import DEFAULT_NAME, DOMAIN, LOGGER, TIMEOUT

DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class CieloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cielo integration."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.client: CieloClient | None = None

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

            username = getattr(self.client, "username", None)
            if not isinstance(username, str) or not username.strip():
                return {"base": "no_username"}

            devices = await self.client.get_devices_data()
            parsed = getattr(devices, "parsed", None)
            if not parsed:
                return {"base": "no_devices"}

        except AuthenticationError:
            return {"base": "invalid_auth"}
        except ConnectionError, TimeoutError, ClientError, CieloError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during config flow validation")
            return {"base": "unknown"}

        return {CONF_TOKEN: token}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input:
            api_key = user_input[CONF_API_KEY].strip()

            validation_result = await self._async_validate_api_key(api_key)

            if "base" in validation_result:
                errors = validation_result
            else:
                token: str = validation_result[CONF_TOKEN]

                user_input[CONF_API_KEY] = api_key
                user_input[CONF_TOKEN] = token
                assert self.client is not None

                username = getattr(self.client, "username", None)
                if isinstance(username, str) and username:
                    await self.async_set_unique_id(username)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
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
