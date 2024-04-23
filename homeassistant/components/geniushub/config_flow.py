"""Config flow for Geniushub logger integration."""
from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)

from . import validate_input
from .const import (
    DEFAULT_GENIISHUB_MAC,
    DEFAULT_GENIISHUB_TOKEN,
    DEFAULT_GENIUSHUB_HOST,
    DEFAULT_GENIUSHUB_PASSWORD,
    DEFAULT_GENIUSHUB_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def step_user_data_schema() -> Schema:
    """User data schema."""
    STEP_USER_DATA_SCHEMA = vol.Schema(
        {vol.Optional("option_1_or_2", default=True): bool}, extra=vol.PREVENT_EXTRA
    )
    return STEP_USER_DATA_SCHEMA


def step_user_data_schema_v1() -> Schema:
    """Validate the user input allows us to connect."""
    data = {
        CONF_HOST: DEFAULT_GENIUSHUB_HOST,
        CONF_PASSWORD: DEFAULT_GENIUSHUB_PASSWORD,
        CONF_USERNAME: DEFAULT_GENIUSHUB_USERNAME,
    }

    STEP_USER_DATA_SCHEMA_V1 = vol.Schema(
        {
            vol.Required(CONF_HOST, default=data.get(CONF_HOST)): str,
            vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD)): str,
        },
        extra=vol.PREVENT_EXTRA,
    )
    return STEP_USER_DATA_SCHEMA_V1


def step_user_data_schema_v3() -> Schema:
    """User data schema for version 3 API."""
    data = {
        CONF_MAC: DEFAULT_GENIISHUB_MAC,
        CONF_TOKEN: DEFAULT_GENIISHUB_TOKEN,
    }
    STEP_USER_DATA_SCHEMA_V3 = vol.Schema(
        {
            vol.Required(CONF_TOKEN, default=data.get(CONF_TOKEN)): str,
            vol.Optional(CONF_MAC, default=data.get(CONF_MAC)): str,
        },
        extra=vol.PREVENT_EXTRA,
    )
    return STEP_USER_DATA_SCHEMA_V3


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
                step_id="user", data_schema=step_user_data_schema()
            )

        if user_input.get("option_1_or_2", False):
            return await self.async_step_user_v1()
        return await self.async_step_user_v3()

    async def async_step_user_v1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="user_v1", data_schema=step_user_data_schema_v1()
            )

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
            data_schema=step_user_data_schema(),
            errors=errors,
        )

    async def async_step_user_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user_v3: ", extra=user_input
        )
        if user_input is None:
            return self.async_show_form(
                step_id="user_v3", data_schema=step_user_data_schema_v3()
            )

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
            data_schema=step_user_data_schema(),
            errors=errors,
        )
