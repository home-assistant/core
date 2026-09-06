"""Config flow for the Linksys Smart Wi-Fi integration."""

import logging
from typing import Any, override

from jnap import JNAPClient, JNAPError, JNAPUnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _async_validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Validate user input allows us to connect and map exceptions to form errors."""
    kwargs: dict[str, Any] = {}
    if username := data.get(CONF_USERNAME):
        kwargs["username"] = username
    client = JNAPClient(
        data[CONF_HOST], async_get_clientsession(hass), data[CONF_PASSWORD], **kwargs
    )
    errors: dict[str, str] = {}
    info: dict[str, Any] | None = None
    try:
        device_info = await client.get_device_info()
        await client.get_devices()
    except JNAPUnauthorizedError:
        errors["base"] = "invalid_auth"
    except JNAPError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        info = {
            "title": device_info.description,
            "serial_number": device_info.serial_number,
        }
    return info, errors


class LinksysConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for linksys."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            info, errors = await _async_validate_input(self.hass, user_input)
            if info is not None:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        else:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
