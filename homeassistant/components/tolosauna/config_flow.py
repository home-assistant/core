"""Config flow for tolosauna."""

import logging
from typing import Any, Dict, Optional

from tololib import ToloClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from ...helpers.device_registry import format_mac
from ..dhcp import IP_ADDRESS, MAC_ADDRESS
from .const import DEFAULT_NAME, DEFAULT_RETRY_COUNT, DEFAULT_RETRY_TIMEOUT, DOMAIN

DATA_SCHEMA_USER = vol.Schema({vol.Required(CONF_HOST): str})


_LOGGER = logging.getLogger(__name__)


class ToloSaunaConfigFlow(ConfigFlow, domain=DOMAIN):
    """ConfigFlow for TOLO Sauna."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize ToloSaunaConfigFlow."""
        self._discovered_host: Optional[str] = None

    @staticmethod
    def _check_device_availability(host: str) -> bool:
        client = ToloClient(host)
        result = client.get_status_info(
            resend_timeout=DEFAULT_RETRY_TIMEOUT, retries=DEFAULT_RETRY_COUNT
        )
        if result is None:
            return False
        else:
            return True

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            device_available = await self.hass.async_add_executor_job(
                self._check_device_availability, user_input[CONF_HOST]
            )

            if not device_available:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={CONF_HOST: user_input[CONF_HOST]}
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )

    async def async_step_dhcp(self, discovery_info: Dict[str, str]) -> FlowResult:
        """Handle a flow initialized by discovery."""
        await self.async_set_unique_id(format_mac(discovery_info[MAC_ADDRESS]))
        self._abort_if_unique_id_configured()
        self._async_abort_entries_match({CONF_HOST: discovery_info[IP_ADDRESS]})

        device_available = await self.hass.async_add_executor_job(
            self._check_device_availability, discovery_info[IP_ADDRESS]
        )

        if device_available:
            self._discovered_host = discovery_info[IP_ADDRESS]
            return await self.async_step_confirm()
        else:
            return self.async_abort(reason="not_tolosauna_device")

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: self._discovered_host})
            return self.async_create_entry(
                title=DEFAULT_NAME, data={CONF_HOST: self._discovered_host}
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_HOST: self._discovered_host},
        )
