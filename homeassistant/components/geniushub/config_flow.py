"""Config flow for Geniushub logger integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from . import validate_input
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

Cloud_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_MAC): cv.string,  # vol.Match(MAC_ADDRESS_REGEXP),
    }
)


Local_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MAC): cv.string,  # vol.Match(MAC_ADDRESS_REGEXP),
    }
)


class GeniusHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis logger."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User config step for determine v1 or v3."""
        _LOGGER.debug("ConfigFlow.async_step_user")
        return self.async_show_menu(
            step_id="user",
            menu_options=["local_api", "cloud_api"],
        )

    async def async_step_local_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        _LOGGER.debug("ConfigFlow.async_step_local_api: ", extra=user_input)
        if user_input is None:
            return self.async_show_form(
                step_id="local_api", data_schema=Local_API_SCHEMA
            )

        self._async_abort_entries_match(user_input)
        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

        except socket.gaierror:
            errors["base"] = "invalid_host"

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized"
            else:
                errors["base"] = "invalid_host"

        except (TimeoutError, aiohttp.ClientConnectionError):
            errors["base"] = "cannot_connect"

        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "ConfigFlow.async_step_local_api: validation passed:",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "ConfigFlow.async_step_local_api: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )

    async def async_step_cloud_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        _LOGGER.debug("ConfigFlow.async_step_cloud_api: ", extra=user_input)
        if user_input is None:
            return self.async_show_form(
                step_id="cloud_api", data_schema=Cloud_API_SCHEMA
            )

        self._async_abort_entries_match(user_input)
        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized_token"
            else:
                errors["base"] = "invalid_host"

        except socket.gaierror:
            errors["base"] = "invalid_host"

        except (TimeoutError, aiohttp.ClientConnectionError):
            errors["base"] = "cannot_connect"

        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Error in genius hub client", exc_info=e)
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "ConfigFlow.async_step_cloud_api: validation passed: ",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "ConfigFlow.async_step_cloud_api: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        self._async_abort_entries_match(user_input)
        errors = {}
        # return self.async_create_entry(title="title", data=user_input)

        try:
            info = await validate_input(self.hass, user_input)

        except socket.gaierror:
            errors["base"] = "invalid_host"

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized"
            else:
                errors["base"] = "invalid_host"

        except TimeoutError:
            errors["base"] = "cannot_connect"

        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"

        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Error in genius hub client", exc_info=e)
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "ConfigFlow.async_step_import: validation passed:",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "ConfigFlow.async_step_import: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )
