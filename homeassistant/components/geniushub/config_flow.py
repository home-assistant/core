"""Config flow for Geniushub integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp
from geniushubclient import GeniusService
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CLOUD_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
    }
)


LOCAL_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class GeniusHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Geniushub."""

    VERSION = 1

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
            service = GeniusService(
                user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                response = await service.request("GET", "auth/release")
            except socket.gaierror:
                errors["base"] = "invalid_host"
            except aiohttp.ClientResponseError as err:
                if err.status == HTTPStatus.UNAUTHORIZED:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "invalid_host"
            except (TimeoutError, aiohttp.ClientConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
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
            service = GeniusService(
                user_input[CONF_TOKEN], session=async_get_clientsession(self.hass)
            )
            try:
                await service.request("GET", "version")
            except aiohttp.ClientResponseError as err:
                if err.status == HTTPStatus.UNAUTHORIZED:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "invalid_host"
            except socket.gaierror:
                errors["base"] = "invalid_host"
            except (TimeoutError, aiohttp.ClientConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Genius hub", data=user_input)

        return self.async_show_form(
            step_id="cloud_api", errors=errors, data_schema=CLOUD_API_SCHEMA
        )
