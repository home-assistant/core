"""Config flow for Imeon integration."""

import logging
from typing import Any
from urllib.parse import urlparse

from imeon_inverter_api.inverter import Inverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImeonInverterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    _host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # User have to provide the hostname if device is not discovered
            host = self._host or user_input[CONF_HOST]

            async with Inverter(host) as client:
                try:
                    # Check connection
                    if await client.login(
                        user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                    ):
                        serial = await client.get_serial()

                    else:
                        errors["base"] = "invalid_auth"

                except TimeoutError:
                    errors["base"] = "cannot_connect"

                except ValueError as e:
                    if "Host invalid" in str(e):
                        errors["base"] = "invalid_host"

                    elif "Route invalid" in str(e):
                        errors["base"] = "invalid_route"

                    else:
                        errors["base"] = "unknown"
                        _LOGGER.exception(
                            "Unexpected error occurred while connecting to the Imeon"
                        )

                if not errors:
                    # Check if entry already exists
                    await self.async_set_unique_id(serial, raise_on_progress=False)
                    self._abort_if_unique_id_configured()

                    # Create a new configuration entry if login succeeds
                    return self.async_create_entry(
                        title=f"Imeon {serial}", data={CONF_HOST: host, **user_input}
                    )

        host_schema: VolDictType = (
            {vol.Required(CONF_HOST): str} if not self._host else {}
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    **host_schema,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a SSDP discovery."""

        host = str(urlparse(discovery_info.ssdp_location).hostname)
        serial = discovery_info.upnp.get(ATTR_UPNP_SERIAL, "")

        if not serial:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._host = host

        self.context["title_placeholders"] = {
            "model": discovery_info.upnp.get(ATTR_UPNP_MODEL_NUMBER, ""),
            "serial": serial,
        }

        return await self.async_step_user()
