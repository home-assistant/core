"""Config flow for Ghost integration."""

from __future__ import annotations

import logging
from typing import Any

from aioghost import GhostAdminAPI
from aioghost.exceptions import GhostAuthError, GhostError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ADMIN_API_KEY, CONF_API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL): str,
        vol.Required(CONF_ADMIN_API_KEY): str,
    }
)


class GhostConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ghost."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            admin_api_key = user_input[CONF_ADMIN_API_KEY]

            if ":" not in admin_api_key:
                errors["base"] = "invalid_api_key"
            else:
                result = await self._validate_and_create(api_url, admin_api_key, errors)
                if result:
                    return result

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://account.ghost.org/?r=settings/integrations/new"
            },
        )

    async def _validate_credentials(
        self, api_url: str, admin_api_key: str
    ) -> dict[str, Any]:
        """Validate credentials against the Ghost API.

        Returns site data on success. Raises GhostAuthError or GhostError on failure.
        """
        api = GhostAdminAPI(
            api_url, admin_api_key, session=async_get_clientsession(self.hass)
        )
        return await api.get_site()

    async def _validate_and_create(
        self,
        api_url: str,
        admin_api_key: str,
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate credentials and create entry."""
        try:
            site = await self._validate_credentials(api_url, admin_api_key)
        except GhostAuthError:
            errors["base"] = "invalid_auth"
            return None
        except GhostError:
            errors["base"] = "cannot_connect"
            return None
        except Exception:
            _LOGGER.exception("Unexpected error during Ghost setup")
            errors["base"] = "unknown"
            return None

        site_title = site["title"]

        await self.async_set_unique_id(site["uuid"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=site_title,
            data={
                CONF_API_URL: api_url,
                CONF_ADMIN_API_KEY: admin_api_key,
            },
        )
