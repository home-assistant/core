"""Config flow to configure the Twinkly integration."""

import logging
from typing import Any, override

from aiohttp import ClientError
from probatio import Required, Schema
from ttls.client import Twinkly

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEV_ID, DEV_MODEL, DEV_NAME, DEVICE_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TwinklyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle twinkly config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: tuple[dict[str, Any], str] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config steps."""
        host = user_input[CONF_HOST] if user_input else None

        schema = {Required(CONF_HOST, default=host): str}
        errors = {}

        if host is not None:
            if (device_info := await self._async_get_device_info(host)) is None:
                errors[CONF_HOST] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    device_info["mac"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self._create_entry_from_device(device_info, host)

        return self.async_show_form(
            step_id="user", data_schema=Schema(schema), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device host."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            device_info = await self._async_get_device_info(user_input[CONF_HOST])
            if device_info is None:
                errors[CONF_HOST] = "cannot_connect"
            else:
                if reconfigure_entry.minor_version == 1:
                    # The MAC migration has not run yet, keep the legacy unique ID
                    if device_info[DEV_ID] != reconfigure_entry.data[CONF_ID]:
                        return self.async_abort(reason="unique_id_mismatch")
                else:
                    await self.async_set_unique_id(device_info["mac"])
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                Schema({Required(CONF_HOST): str}),
                user_input or reconfigure_entry.data,
            ),
            errors=errors,
        )

    async def _async_get_device_info(self, host: str) -> dict[str, Any] | None:
        """Fetch the device details, or None if the device cannot be reached."""
        try:
            return await Twinkly(
                host, async_get_clientsession(self.hass), timeout=DEVICE_TIMEOUT
            ).get_details()
        except TimeoutError, ClientError:
            return None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery for twinkly."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})
        try:
            device_info = await Twinkly(
                discovery_info.ip,
                async_get_clientsession(self.hass),
                timeout=DEVICE_TIMEOUT,
            ).get_details()
        except TimeoutError, ClientError:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(device_info["mac"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        self._discovered_device = (device_info, discovery_info.ip)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device_info, host = self._discovered_device

        if user_input is not None:
            return self._create_entry_from_device(device_info, host)

        self.context["title_placeholders"] = {
            "name": device_info[DEV_NAME],
        }
        placeholders = {
            "model": device_info[DEV_MODEL],
            "name": device_info[DEV_NAME],
            "host": host,
        }
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    def _create_entry_from_device(
        self, device_info: dict[str, Any], host: str
    ) -> ConfigFlowResult:
        """Create entry from device data."""
        return self.async_create_entry(
            title=device_info[DEV_NAME],
            data={
                CONF_HOST: host,
                CONF_ID: device_info[DEV_ID],
                CONF_NAME: device_info[DEV_NAME],
                CONF_MODEL: device_info[DEV_MODEL],
            },
        )
