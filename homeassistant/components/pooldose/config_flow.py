"""Config flow for the Seko PoolDose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Pooldose integration including DHCP discovery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow and store the discovered IP address."""
        super().__init__()
        self._discovered_ip: str | None = None

    async def _validate_host(
        self, host: str
    ) -> tuple[str | None, dict[str, str] | None, dict[str, str] | None]:
        """Validate the host and return (serial_number, api_versions, errors)."""
        client = PooldoseClient(host)
        client_status = await client.connect()
        if client_status == RequestStatus.HOST_UNREACHABLE:
            return None, None, {"base": "cannot_connect"}
        if client_status == RequestStatus.PARAMS_FETCH_FAILED:
            return None, None, {"base": "params_fetch_failed"}
        if client_status != RequestStatus.SUCCESS:
            return None, None, {"base": "cannot_connect"}

        api_status, api_versions = client.check_apiversion_supported()
        if api_status == RequestStatus.NO_DATA:
            return None, None, {"base": "api_not_set"}
        if api_status == RequestStatus.API_VERSION_UNSUPPORTED:
            return None, api_versions, {"base": "api_not_supported"}

        device_info = client.device_info
        if not device_info:
            return None, None, {"base": "no_device_info"}
        serial_number = device_info.get("SERIAL_NUMBER")
        if not serial_number:
            return None, None, {"base": "no_serial_number"}

        return serial_number, None, None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a simple DHCP discovery: abort if already configured, else show a confirmation dialog."""

        # test outputs, use MAC later to complete the connection attribute of existing devices
        _LOGGER.debug("DHCP discovery IP address  %s", discovery_info.ip)
        _LOGGER.debug("DHCP discovery MAC address %s", discovery_info.macaddress)
        serial_number, _, _ = await self._validate_host(discovery_info.ip)
        if serial_number:
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
            self._discovered_ip = discovery_info.ip
            return self.async_show_form(
                step_id="dhcp_confirm",
                description_placeholders={
                    "ip": discovery_info.ip,
                    "mac": discovery_info.macaddress,
                    "name": f"PoolDose {serial_number}",
                },
            )
        return self.async_abort(reason="already_configured")

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry after the confirmation dialog."""
        discovered_ip = self._discovered_ip
        return self.async_create_entry(
            title=f"PoolDose {self.unique_id}",
            data={CONF_HOST: discovered_ip},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
            )

        host = user_input[CONF_HOST]
        serial_number, api_versions, errors = await self._validate_host(host)
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors=errors,
                description_placeholders=api_versions,
            )

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"PoolDose {self.unique_id}",
            data={CONF_HOST: host},
        )
