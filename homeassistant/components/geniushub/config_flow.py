"""Config flow for Geniushub logger integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from . import STEP_USER_DATA_SCHEMA, V1_API_SCHEMA, V3_API_SCHEMA, validate_input
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis logger."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User config step for determine v1 or v3."""
        _LOGGER.debug("config_flow.py:ConfigFlow.async_step_user")
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        if user_input.get("option_1_or_2", False):
            return await self.async_step_user_v3()
        return await self.async_step_user_v1()

    async def async_step_user_v1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user_v1: ", extra=user_input
        )
        if user_input is None:
            return self.async_show_form(step_id="user_v1", data_schema=V1_API_SCHEMA)

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
                "config_flow.py:ConfigFlow.async_step_user: validation passed: ",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        if user_input is None:
            return self.async_show_form(step_id="user_v3", data_schema=V3_API_SCHEMA)

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
                "config_flow.py:ConfigFlow.async_step_user: validation passed:",
                extra=user_input,
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
