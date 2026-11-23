"""Config flow for Geniushub integration."""

from collections.abc import Mapping
from http import HTTPStatus
import logging
import socket
from typing import Any, override

import aiohttp
from geniushubclient import GeniusService
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CLOUD_API_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_TOKEN)): str,
    }
)


LOCAL_API_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

LOCAL_REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class GeniusHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Geniushub."""

    VERSION = 1

    async def _async_request(
        self, service: GeniusService, path: str
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Request a path from the hub and map known failures to form errors."""
        errors: dict[str, str] = {}
        response: dict[str, Any] = {}
        try:
            response = await service.request("GET", path)
        except socket.gaierror:
            errors["base"] = "invalid_host"
        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "invalid_host"
        except TimeoutError, aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return response, errors

    async def _async_validate_local(
        self, host: str, username: str, password: str
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Validate the local API credentials."""
        service = GeniusService(
            host,
            username=username,
            password=password,
            session=async_get_clientsession(self.hass),
        )
        return await self._async_request(service, "auth/release")

    async def _async_validate_cloud(self, token: str) -> dict[str, str]:
        """Validate the cloud API token."""
        service = GeniusService(token, session=async_get_clientsession(self.hass))
        _, errors = await self._async_request(service, "version")
        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User config step for determine cloud or local."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["local_api", "cloud_api"],
        )

    async def async_step_local_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
            response, errors = await self._async_validate_local(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                await self.async_set_unique_id(response["data"]["UID"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="local_api", errors=errors, data_schema=LOCAL_API_SCHEMA
        )

    async def async_step_cloud_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            errors = await self._async_validate_cloud(user_input[CONF_TOKEN])
            if not errors:
                return self.async_create_entry(title="Genius hub", data=user_input)

        return self.async_show_form(
            step_id="cloud_api", errors=errors, data_schema=CLOUD_API_SCHEMA
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a failed authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials for the API mode the entry uses."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if CONF_TOKEN in reauth_entry.data:
            if user_input is not None:
                errors = await self._async_validate_cloud(user_input[CONF_TOKEN])
                if not errors:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input
                    )
            return self.async_show_form(
                step_id="reauth_confirm",
                errors=errors,
                data_schema=CLOUD_API_SCHEMA,
            )

        if user_input is not None:
            response, errors = await self._async_validate_local(
                reauth_entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                await self.async_set_unique_id(response["data"]["UID"])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                LOCAL_REAUTH_SCHEMA,
                {CONF_USERNAME: (user_input or reauth_entry.data)[CONF_USERNAME]},
            ),
        )
