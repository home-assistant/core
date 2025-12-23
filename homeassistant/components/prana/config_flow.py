"""Configuration flow for Prana integration discovered via Zeroconf.

The flow is discovery-only. Users confirm a found device; manual starts abort.
"""

import logging
from typing import Any

from prana_local_api_client.exceptions import PranaApiCommunicationError
from prana_local_api_client.models.prana_device_info import PranaDeviceInfo
from prana_local_api_client.prana_api_client import PranaLocalApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_BASE, CONF_HOST
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

SERVICE_TYPE = "_prana._tcp.local."

_LOGGER = logging.getLogger(__name__)


class PranaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Prana config flow."""

    def __init__(self) -> None:
        """Initialize the Prana config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._device_info: PranaDeviceInfo | None = None
        self.context = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of a Prana device."""
        _LOGGER.debug("Discovered device via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        friendly_name = discovery_info.properties.get("label", "")
        self.context["title_placeholders"] = {"name": friendly_name}
        self._host = host

        return await self.async_step_confirm()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Manual entry by IP address."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self.async_step_confirm()

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation form or create entry when submitted."""
        if not self._host:
            return self.async_abort(reason="no_devices_found")

        api_client = PranaLocalApiClient(host=self._host, port=80)
        try:
            device_info = await api_client.get_device_info()
        except PranaApiCommunicationError as err:
            _LOGGER.debug("Error fetching device info from %s: %s", self._host, err)
            return await self.async_step_user(
                errors={CONF_BASE: "invalid_device_or_unreachable"}
            )
        if not device_info.isValid:
            return self.async_abort(reason="invalid_device")

        await self.async_set_unique_id(device_info.manufactureId)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=device_info.label,
                data={
                    CONF_HOST: self._host,
                },
                description_placeholders={
                    "name": device_info.label,
                    "host": self._host,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": device_info.label,
                "host": self._host,
            },
        )
