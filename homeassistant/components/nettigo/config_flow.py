"""Adds config flow for Nettigo."""
import asyncio
import logging
from typing import Optional

from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from nettigo import ApiError, CannotGetMac, Nettigo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class NettigoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nettigo."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    host = None

    async def async_step_user(self, user_input: Optional[ConfigType] = None) -> dict:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                mac = await self._async_get_mac(host)
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except CannotGetMac:
                return self.async_abort(reason="device_unsupported")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:

                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured({CONF_HOST: host})

                return self.async_create_entry(
                    title=host,
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

    async def async_step_zeroconf(self, zeroconf_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        self.host = zeroconf_info[CONF_HOST]

        try:
            mac = await self._async_get_mac(self.host)
        except (ApiError, ClientConnectorError, asyncio.TimeoutError):
            return self.async_abort(reason="cannot_connect")
        except CannotGetMac:
            return self.async_abort(reason="device_unsupported")

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        self.context["title_placeholders"] = {
            ATTR_NAME: zeroconf_info[ATTR_NAME].split(".")[0]
        }

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(self, user_input=None):
        """Handle discovery confirm."""
        errors = {}

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
        nettigo = Nettigo(websession, host)
        # Device firmware uses synchronous code and doesn't respond to http queries
        # when reading data from sensors. The nettigo library tries to get the data
        # 4 times, so we use a longer than usual timeout here.
        with async_timeout.timeout(30):
            return await nettigo.async_get_mac_address()
