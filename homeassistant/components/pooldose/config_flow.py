"""Config flow for the Seko PoolDose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        """Initialize the config flow and store the discovered IP address and MAC."""
        super().__init__()
        self._discovered_ip: str | None = None
        self._discovered_mac: str | None = None

    async def _validate_host(
        self, host: str
    ) -> tuple[str | None, dict[str, str] | None, dict[str, str] | None]:
        """Validate the host and return (serial_number, api_versions, errors)."""
        client = PooldoseClient(host, websession=async_get_clientsession(self.hass))
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
        """Handle DHCP discovery: validate device and update IP if needed."""
        serial_number, _, _ = await self._validate_host(discovery_info.ip)
        if not serial_number:
            return self.async_abort(reason="no_serial_number")

        # If an existing entry is found
        existing_entry = await self.async_set_unique_id(serial_number)
        if existing_entry:
            # Only update the MAC if it's not already set
            if CONF_MAC not in existing_entry.data:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={**existing_entry.data, CONF_MAC: discovery_info.macaddress},
                )
            self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        # Else: Continue with new flow
        self._discovered_ip = discovery_info.ip
        self._discovered_mac = discovery_info.macaddress
        return self.async_show_form(
            step_id="dhcp_confirm",
            description_placeholders={
                "ip": discovery_info.ip,
                "mac": discovery_info.macaddress,
                "name": f"PoolDose {serial_number}",
            },
        )

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry after the confirmation dialog."""
        return self.async_create_entry(
            title=f"PoolDose {self.unique_id}",
            data={
                CONF_HOST: self._discovered_ip,
                CONF_MAC: self._discovered_mac,
            },
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

        await self.async_set_unique_id(serial_number, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"PoolDose {serial_number}",
            data={CONF_HOST: host},
        )
