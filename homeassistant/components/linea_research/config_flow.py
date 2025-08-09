"""Config flow for Linea Research integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN, NAME
from .tipi_client import TIPIClient, TIPIConnectionError, TIPIProtocolError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = TIPIClient(data[CONF_HOST], data[CONF_PORT])
    
    try:
        await client.connect()
        info = await client.get_device_info()
        await client.disconnect()
        
        return {
            "title": f"{NAME} {info.get('model', 'Amplifier')}",
            "unique_id": info.get("serial", f"{data[CONF_HOST]}:{data[CONF_PORT]}"),
        }
    except TIPIConnectionError as err:
        _LOGGER.error("Failed to connect: %s", err)
        raise CannotConnect from err
    except TIPIProtocolError as err:
        _LOGGER.error("Protocol error: %s", err)
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected error: %s", err)
        raise CannotConnect from err
    finally:
        await client.disconnect()


class LineaResearchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Linea Research."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""