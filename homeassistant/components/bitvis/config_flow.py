"""Config flow for the Bitvis Power Hub integration."""

import logging
from typing import Any

from bitvis_protobuf.utils import (
    async_verify_udp_port_bindable,
    get_mac_address_for_host,
    normalize_host,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, MODEL_NAME
from .coordinator import async_get_listener_registry

_LOGGER = logging.getLogger(__name__)


async def _async_test_port(hass: HomeAssistant, port: int) -> None:
    """Verify the UDP port can be bound."""

    if async_get_listener_registry(hass).has_listener(port):
        return

    await async_verify_udp_port_bindable(port)


async def _async_get_device_unique_id(hass: HomeAssistant, host: str) -> str:
    """Resolve *host* and look up a MAC address for the config entry unique ID."""
    return await hass.async_add_executor_job(get_mac_address_for_host, host)


class BitvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitvis Power Hub."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: ZeroconfServiceInfo | None = None

    def _get_friendly_name(self, name: str | None) -> str:
        """Return a user-friendly name derived from the zeroconf name."""
        if not name:
            return DEFAULT_NAME
        instance = name.split(".", 1)[0]
        return instance or DEFAULT_NAME

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            port = user_input[CONF_PORT]

            try:
                await _async_test_port(self.hass, port)
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    await _async_get_device_unique_id(self.hass, host)
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=MODEL_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered Bitvis Power Hub via Zeroconf: %s", discovery_info)

        host = discovery_info.host

        await self.async_set_unique_id(
            await _async_get_device_unique_id(self.hass, host)
        )
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Show confirmation to user
        self.context["title_placeholders"] = {
            "name": self._get_friendly_name(discovery_info.name),
            "host": host,
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            assert self._discovery_info is not None
            host = self._discovery_info.host
            port = self._discovery_info.port or DEFAULT_PORT

            try:
                await _async_test_port(self.hass, port)
            except OSError:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=self._get_friendly_name(self._discovery_info.name),
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._get_friendly_name(
                    self._discovery_info.name if self._discovery_info else None
                ),
                "host": self._discovery_info.host if self._discovery_info else "",
            },
        )
