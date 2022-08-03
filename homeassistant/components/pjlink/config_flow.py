"""Config flow for PJLink integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_ENCODING, DEFAULT_ENCODING, DEFAULT_PORT, DOMAIN

TITLE = "PJLink"


class PJLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for PJLink."""

    def __init__(self) -> None:
        """Initialize config flow."""
        self.host: str | None = None
        self.port: int | None = None

    # Can we can identify PJLink devices with dhcp or something else?
    # During authentication the library checks that we are talking to a PJLink device
    # https://github.com/benoitlouy/pypjlink/blob/1932aaf7c18113e6281927f4ee2d30c6b8593639/pypjlink/projector.py#L80-L85

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""

        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(
                            CONF_ENCODING, default=DEFAULT_ENCODING
                        ): cv.string,
                        vol.Optional(CONF_PASSWORD): cv.string,
                    }
                ),
            )

        # Process user input
        # How to generate a unique ID?
        # The PJLink API does not expose MAC address or serial number, only name, manufacturer, and model
        # Can we get the MAC address from the IP address?
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        name = user_input[CONF_NAME]
        password = user_input[CONF_PASSWORD]
        # await self.async_set_unique_id(serial_number, raise_on_progress=False)
        # self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
                CONF_PASSWORD: password,
            },
        )

    # avahi/zeroconf
    # looks like there are these services that should be discoverable according
    # to https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml?search=pjlink
    #   _pjlink._tcp
    #   _pjlink._udp
    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        mac_addr = format_mac(discovery_info.properties["macaddress"])
        self.host = discovery_info.host
        self.port = discovery_info.port
        await self.async_set_unique_id(
            mac_addr
        )  # How can we deal with this outside zeroconf?
        self._abort_if_unique_id_configured()
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Confirm the setup."""

        if user_input is None:
            assert self.host
            assert self.port
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    CONF_NAME: self.unique_id,
                    CONF_HOST: self.host,
                    CONF_PORT: str(self.port),
                    CONF_ENCODING: DEFAULT_ENCODING,
                    CONF_PASSWORD: None,
                },
            )

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        name = user_input[CONF_NAME]
        password = user_input[CONF_PASSWORD]
        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
                CONF_PASSWORD: password,
            },
        )
