"""Config flow for the Ubiquiti airOS integration."""

from __future__ import annotations

import logging
from typing import Any

from airos.airos8 import AirOS
from airos.exceptions import (
    ConnectionAuthenticationError,
    ConnectionSetupError,
    DataMissingError,
    DeviceConnectionError,
    KeyDataMissingError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AIROS_DEFAULT_HOSTNAME,
    AIROS_DEVICE_ID_KEY,
    AIROS_HOST_KEY,
    AIROS_HOSTNAME_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="ubnt"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AirOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ubiquiti airOS."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        hass: HomeAssistant | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # By default airOS 8 comes with self-signed SSL certificates,
            # with no option in the web UI to change or upload a custom certificate.
            session = async_get_clientsession(self.hass, verify_ssl=False)

            airos_device = AirOS(
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )
            try:
                await airos_device.login()
                status = await airos_device.status()

            except (
                ConnectionSetupError,
                DeviceConnectionError,
            ):
                errors["base"] = "cannot_connect"
            except (ConnectionAuthenticationError, DataMissingError):
                errors["base"] = "invalid_auth"
            except KeyDataMissingError:
                errors["base"] = "key_data_missing"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                host_data: dict[str, Any] = status[AIROS_HOST_KEY]
                device_id: str = host_data[AIROS_DEVICE_ID_KEY]
                hostname: str = host_data.get(
                    AIROS_HOSTNAME_KEY, AIROS_DEFAULT_HOSTNAME
                )

                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=hostname, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
