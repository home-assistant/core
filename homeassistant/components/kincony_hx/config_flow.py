"""Config flow for KinCony Hx integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from . import CannotConnect, KCBoard
from .const import (
    CONF_REFRESH,
    CONF_SO_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_REFRESH,
    DEFAULT_SO_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def get_schema_with_data(data: dict[str, Any] | None = None) -> vol.Schema:
    """Retrieve the schema with updateable defaults from data."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=data.get(CONF_HOST, None) if data else None,
            ): cv.string,
            vol.Optional(
                CONF_NAME,
                default=data.get(CONF_NAME, DEFAULT_NAME) if data else DEFAULT_NAME,
            ): cv.string,
            vol.Optional(
                CONF_PORT,
                default=data.get(CONF_PORT, DEFAULT_PORT) if data else DEFAULT_PORT,
            ): cv.port,
            vol.Optional(
                CONF_REFRESH,
                default=data.get(CONF_REFRESH, DEFAULT_REFRESH)
                if data
                else DEFAULT_REFRESH,
            ): cv.positive_int,
            vol.Optional(
                CONF_SO_TIMEOUT,
                default=data.get(CONF_SO_TIMEOUT, DEFAULT_SO_TIMEOUT)
                if data
                else DEFAULT_SO_TIMEOUT,
            ): cv.positive_int,
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the specified endpoint is accessible."""
    client = KCBoard.from_data(data)

    relays_count = 0
    try:
        client.connect()
        relays_count = client.read_relays_count()
        client.dispose()
    except ConnectionRefusedError:
        raise
    except OSError as exception:
        raise CannotConnect from exception

    # Return info that you want to store in the config entry.
    return {
        "title": data.get(CONF_NAME, DEFAULT_NAME),
        "desc": f"KinCony Board with {relays_count} relays at {data[CONF_HOST]}",
    }


class KCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KinCony Hx."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=get_schema_with_data()
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except ConnectionRefusedError:
            errors["base"] = "connect_refused"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"], description=info["desc"], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=get_schema_with_data(user_input), errors=errors
        )
