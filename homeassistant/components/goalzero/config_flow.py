"""Config flow for Goal Zero Yeti integration."""
from __future__ import annotations

import logging
from typing import Any

from goalzero import Yeti, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required("host"): str, vol.Required("name"): str})


class GoalZeroFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goal Zero Yeti."""

    VERSION = 1

    def __init__(self):
        """Initialize a Goal Zero Yeti flow."""
        self.ip_address = None

    async def async_step_dhcp(self, discovery_info):
        """Handle dhcp discovery."""
        self.ip_address = discovery_info[IP_ADDRESS]

        await self.async_set_unique_id(discovery_info[MAC_ADDRESS])
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.ip_address})
        self._async_abort_entries_match({CONF_HOST: self.ip_address})

        _, error = await self._async_try_connect(self.ip_address)
        if error is None:
            return await self.async_step_confirm_discovery()
        return self.async_abort(reason=error)

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
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            self._async_abort_entries_match({CONF_HOST: host})

            mac_address, error = await self._async_try_connect(host)
            if error is None:
                await self.async_set_unique_id(format_mac(mac_address))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST) or ""
                    ): str,
                    vol.Optional(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self, host):
        """Try connecting to Goal Zero Yeti."""
        try:
            session = async_get_clientsession(self.hass)
            api = Yeti(host, self.hass.loop, session)
            await api.sysinfo()
        except exceptions.ConnectError:
            _LOGGER.error("Error connecting to device at %s", host)
            return None, "cannot_connect"
        except exceptions.InvalidHost:
            _LOGGER.error("Invalid host at %s", host)
            return None, "invalid_host"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return str(api.sysdata["macAddress"]), None
