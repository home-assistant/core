"""Adds config flow for Nettigo Air Monitor."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from nettigo_air_monitor import ApiError, CannotGetMac, NettigoAirMonitor
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NAMFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nettigo Air Monitor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize flow."""
        self.host: str = None  # type: ignore[assignment]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]
            try:
                mac = await self._async_get_mac(self.host)
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except CannotGetMac:
                return self.async_abort(reason="device_unsupported")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:

                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                return self.async_create_entry(
                    title=self.host,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info[CONF_HOST]

        try:
            mac = await self._async_get_mac(self.host)
        except (ApiError, ClientConnectorError, asyncio.TimeoutError):
            return self.async_abort(reason="cannot_connect")
        except CannotGetMac:
            return self.async_abort(reason="device_unsupported")

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        self.context["title_placeholders"] = {
            ATTR_NAME: discovery_info[ATTR_NAME].split(".")[0]
        }

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery confirm."""
        errors: dict = {}

        if user_input is not None:
            return self.async_create_entry(
                title=self.host,
                data={CONF_HOST: self.host},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={CONF_HOST: self.host},
            errors=errors,
        )

    async def _async_get_mac(self, host: str) -> str:
        """Get device MAC address."""
        websession = async_get_clientsession(self.hass)
        nam = NettigoAirMonitor(websession, host)
        # Device firmware uses synchronous code and doesn't respond to http queries
        # when reading data from sensors. The nettigo-air-monitor library tries to get
        # the data 4 times, so we use a longer than usual timeout here.
        with async_timeout.timeout(30):
            return cast(str, await nam.async_get_mac_address())
