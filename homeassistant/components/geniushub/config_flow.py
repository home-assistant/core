"""Config flow for Geniushub logger integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from . import V1_API_SCHEMA, V3_API_SCHEMA, validate_input
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
            menu_options=["v3_api", "v1_api"],
        )

    async def async_step_v3_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        _LOGGER.debug("ConfigFlow.async_step_v3_api: ", extra=user_input)
        if user_input is None:
            return self.async_show_form(step_id="v3_api", data_schema=V3_API_SCHEMA)

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

        except TimeoutError:
            errors["base"] = "cannot_connect"

        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "ConfigFlow.async_step_v3_api: validation passed:",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "ConfigFlow.async_step_v3_api: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )

    async def async_step_v1_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        _LOGGER.debug("ConfigFlow.async_step_v1_api: ", extra=user_input)
        if user_input is None:
            return self.async_show_form(step_id="v1_api", data_schema=V1_API_SCHEMA)

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

        except TimeoutError:
            errors["base"] = "cannot_connect"

        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "ConfigFlow.async_step_v1_api: validation passed: ",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "ConfigFlow.async_step_v1_api: validation failed: ",
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

        except Exception:  # pylint: disable=broad-except
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
