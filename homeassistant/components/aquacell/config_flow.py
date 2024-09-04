"""Config flow for Aquacell integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from aioaquacell import ApiException, AquacellApi, AuthenticationFailed
from aioaquacell.const import SUPPORTED_BRANDS, Brand
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BRAND,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BRAND, default=Brand.AQUACELL): vol.In(
            {key: brand.name for key, brand in SUPPORTED_BRANDS.items()}
        ),
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AquaCellConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aquacell."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud logon step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                user_input[CONF_EMAIL].lower(), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = AquacellApi(session, user_input[CONF_BRAND])
            try:
                refresh_token = await api.authenticate(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except ApiException:
                errors["base"] = "cannot_connect"
            except AuthenticationFailed:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        **user_input,
                        CONF_BRAND: user_input[CONF_BRAND],
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
