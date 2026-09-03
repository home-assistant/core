"""Config flow for the WATERCryst integration."""

import logging
from typing import Any, override

from httpx import HTTPStatusError, RequestError
from pyocat import (
    AsyncApiClient,
    AsyncAuth,
    WTCApiDisabledError,
    WTCApiTemporaryError,
    WTCApiUnauthorizedError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class WatercrystConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WATERCryst devices."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input:
            key = user_input[CONF_API_KEY]
            auth = AsyncAuth(client=get_async_client(self.hass), api_key=key)
            client = AsyncApiClient(auth=auth)

            try:
                info = await client.get_device_info()
            except WTCApiDisabledError:
                errors["base"] = "api_disabled"
            except WTCApiUnauthorizedError:
                errors["base"] = "invalid_auth"
            except WTCApiTemporaryError:
                errors["base"] = "cannot_connect"
            except HTTPStatusError:
                errors["base"] = "cannot_connect"
            except RequestError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.biocat_serial)
                self._abort_if_unique_id_configured()

                title = info.name or info.biocat_serial
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_STEP_USER_DATA_SCHEMA, errors=errors
        )
