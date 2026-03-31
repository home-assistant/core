"""Config flow for the CentriConnect/MyPropane API integration."""

from __future__ import annotations

import logging
from typing import Any

from aiocentriconnect import CentriConnect
from aiocentriconnect.exceptions import (
    CentriConnectConnectionError,
    CentriConnectDecodeError,
    CentriConnectEmptyResponseError,
    CentriConnectNotFoundError,
    CentriConnectTooManyRequestsError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CENTRICONNECT_DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Validate the user-supplied data can be used to set up a connection.
    hub = CentriConnect(
        data[CONF_USERNAME],
        data[CONF_DEVICE_ID],
        data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    tank_data = await hub.async_get_tank_data()

    # Return info to store in the config entry.
    return {
        "title": tank_data.device_name,
        CENTRICONNECT_DEVICE_ID: tank_data.device_id,
    }


class CentriConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CentriConnect/MyPropane API."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CentriConnectConnectionError:
                errors["base"] = "cannot_connect"
            except CentriConnectTooManyRequestsError:
                errors["base"] = "cannot_connect"
            except CentriConnectNotFoundError:
                errors["base"] = "invalid_auth"
            except CentriConnectEmptyResponseError:
                errors["base"] = "unknown"
            except CentriConnectDecodeError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    unique_id=info[CENTRICONNECT_DEVICE_ID], raise_on_progress=True
                )
                self._abort_if_unique_id_configured(
                    updates=user_input, reload_on_update=True
                )
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
