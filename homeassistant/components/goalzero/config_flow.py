"""Config flow for Goal Zero Yeti integration."""
from __future__ import annotations

from typing import Any

from goalzero import Yeti, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import _LOGGER
from .const import DEFAULT_NAME
from .const import DOMAIN  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema({"host": str, "name": str})


class GoalZeroFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goal Zero Yeti."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the goalzero flow."""
        self.ip_address = None
        self.errors = {}

    async def async_step_dhcp(self, dhcp_discovery):
        """Handle dhcp discovery."""
        self.ip_address = dhcp_discovery[IP_ADDRESS]

        await self.async_try_connect(self.ip_address, DEFAULT_NAME)

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""

        if user_input is not None:
            return self.async_create_entry(
                title="Goal Zero",
                data={
                    CONF_HOST: self.ip_address,
                    CONF_NAME: DEFAULT_NAME,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                CONF_HOST: self.ip_address,
                CONF_NAME: DEFAULT_NAME,
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            await self.async_try_connect(host, name)

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.ip_address): str,
                    vol.Optional(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
                }
            ),
            errors=self.errors,
        )

    async def async_try_connect(self, host, name):
        """Try connecting."""
        try:
            session = async_get_clientsession(self.hass)
            api = Yeti(host, self.hass.loop, session)
            await api.init_connect()
            await self.async_set_unique_id(api.sysdata["macAddress"].lower())
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            for entry in self._async_current_entries():
                if entry.data.get(CONF_HOST) == host:
                    return self.async_abort(reason="already_configured")
                CONF_DATA = {
                    CONF_HOST: host,
                    CONF_NAME: name,
                }
                self.hass.config_entries.async_update_entry(entry, data=CONF_DATA)
                await self.hass.config_entries.async_reload(entry.entry_id)
        except exceptions.ConnectError:
            self.errors["base"] = "cannot_connect"
            _LOGGER.error("Error connecting to device at %s", host)
        except exceptions.InvalidHost:
            self.errors["base"] = "invalid_host"
            _LOGGER.error("Invalid host at %s", host)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            self.errors["base"] = "unknown"
        else:
            return True

    @callback
    def _async_ip_address_already_configured(self, ip_address):
        """See if we already have an entry matching the ip_address."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == ip_address:
                return True
        return False
