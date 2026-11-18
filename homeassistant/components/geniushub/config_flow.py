"""Config flow for Geniushub integration."""

from http import HTTPStatus
import logging
import socket
from typing import Any, override

import aiohttp
from geniushubclient import GeniusService

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_MANUFACTURER, DOMAIN
from .schemas import CLOUD_API_SCHEMA, LOCAL_API_SCHEMA

_LOGGER = logging.getLogger(__name__)


class GeniusHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Geniushub."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User config step for determine cloud or local."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["local_api", "cloud_api"],
        )

    @override
    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        return await self.async_step_user()

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
            except TimeoutError, aiohttp.ClientConnectionError:
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

        if self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                LOCAL_API_SCHEMA, self._get_reconfigure_entry().data
            )
        else:
            data_schema = LOCAL_API_SCHEMA

        return self.async_show_form(
            step_id="local_api", errors=errors, data_schema=data_schema
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
            except TimeoutError, aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=ATTR_MANUFACTURER, data=user_input)

        if self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                CLOUD_API_SCHEMA, self._get_reconfigure_entry().data
            )
        else:
            data_schema = CLOUD_API_SCHEMA

        return self.async_show_form(
            step_id="cloud_api", errors=errors, data_schema=data_schema
        )
