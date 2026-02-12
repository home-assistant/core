"""Config flow for the Homevolt integration."""

from __future__ import annotations

import logging
from typing import Any

from homevolt import Homevolt, HomevoltAuthenticationError, HomevoltConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

STEP_CREDENTIALS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None

    async def check_status(self, client: Homevolt) -> dict[str, str]:
        """Check connection status and return errors if any."""
        errors: dict[str, str] = {}
        try:
            await client.update_info()
        except HomevoltAuthenticationError:
            errors["base"] = "invalid_auth"
        except HomevoltConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Error occurred while connecting to the Homevolt battery")
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            password = None
            websession = async_get_clientsession(self.hass)
            client = Homevolt(host, password, websession=websession)
            errors = await self.check_status(client)
            if errors.get("base") == "invalid_auth":
                self._host = host
                return await self.async_step_credentials()

            if not errors:
                device_id = client.unique_id
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Homevolt",
                    data={
                        CONF_HOST: host,
                        CONF_PASSWORD: None,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        assert self._host is not None

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            websession = async_get_clientsession(self.hass)
            client = Homevolt(self._host, password, websession=websession)
            errors = await self.check_status(client)

            if not errors:
                device_id = client.unique_id
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Homevolt",
                    data={
                        CONF_HOST: self._host,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"host": self._host},
        )
