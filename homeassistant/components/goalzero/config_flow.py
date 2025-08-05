"""Config flow for Goal Zero Yeti integration."""

from __future__ import annotations

import logging
from typing import Any

from goalzero import Yeti, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class GoalZeroFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goal Zero Yeti."""

    VERSION = 1

    _discovered_ip: str

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""

        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})

        _, error = await self._async_try_connect(discovery_info.ip)
        if error is None:
            self._discovered_ip = discovery_info.ip
            return await self.async_step_confirm_discovery()
        return self.async_abort(reason=error)

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=MANUFACTURER,
                data={
                    CONF_HOST: self._discovered_ip,
                    CONF_NAME: DEFAULT_NAME,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                CONF_HOST: self._discovered_ip,
                CONF_NAME: DEFAULT_NAME,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            self._async_abort_entries_match({CONF_HOST: host})

            mac_address, error = await self._async_try_connect(host)
            if error is None:
                await self.async_set_unique_id(format_mac(str(mac_address)))
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

    async def _async_try_connect(self, host: str) -> tuple[str | None, str | None]:
        """Try connecting to Goal Zero Yeti."""
        try:
            api = Yeti(host, async_get_clientsession(self.hass))
            await api.sysinfo()
        except exceptions.ConnectError:
            return None, "cannot_connect"
        except exceptions.InvalidHost:
            return None, "invalid_host"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return str(api.sysdata["macAddress"]), None
