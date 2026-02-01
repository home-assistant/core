"""Config flow for Ghost integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aioghost import GhostAdminAPI
from aioghost.exceptions import GhostAuthError, GhostError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ADMIN_API_KEY, CONF_API_URL, DEFAULT_TITLE, DOMAIN

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

    _reauth_entry: ConfigEntry | None = None

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assert self._reauth_entry is not None
            api_url = self._reauth_entry.data[CONF_API_URL]
            admin_api_key = user_input[CONF_ADMIN_API_KEY]

            if ":" not in admin_api_key:
                errors["base"] = "invalid_api_key"
            else:
                try:
                    await self._validate_credentials(api_url, admin_api_key)
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            CONF_API_URL: api_url,
                            CONF_ADMIN_API_KEY: admin_api_key,
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
                except GhostAuthError:
                    errors["base"] = "invalid_auth"
                except GhostError:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ADMIN_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the API URL."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            admin_api_key = entry.data[CONF_ADMIN_API_KEY]

            try:
                await self._validate_credentials(api_url, admin_api_key)
                await self.async_set_unique_id(api_url)
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_URL: api_url},
                )
            except AbortFlow:
                raise
            except GhostAuthError:
                errors["base"] = "invalid_auth"
            except GhostError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Ghost reconfigure")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL, default=entry.data[CONF_API_URL]): str,
                }
            ),
            errors=errors,
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
        result: dict[str, Any] = await api.get_site()
        return result

    async def _validate_and_create(
        self,
        api_url: str,
        admin_api_key: str,
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate credentials and create entry."""
        try:
            site = await self._validate_credentials(api_url, admin_api_key)
            site_title = site.get("title", DEFAULT_TITLE)

            await self.async_set_unique_id(api_url)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=site_title,
                data={
                    CONF_API_URL: api_url,
                    CONF_ADMIN_API_KEY: admin_api_key,
                },
            )
        except AbortFlow:
            raise
        except GhostAuthError:
            errors["base"] = "invalid_auth"
        except GhostError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during Ghost setup")
            errors["base"] = "unknown"
        return None
