"""Actions for the HTTP integration."""

from ipaddress import IPv4Address, IPv6Address
from typing import Final

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service

from .ban import KEY_BAN_MANAGER
from .const import ATTR_IP_ADDRESS, DOMAIN, IP_ADDRESS

SERVICE_UNBAN: Final = "unban"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the HTTP actions."""

    async def async_unban(call: ServiceCall) -> None:
        """Lift the ban of an IP address."""
        remote_addr: IPv4Address | IPv6Address = call.data[ATTR_IP_ADDRESS]
        if not await hass.http.app[KEY_BAN_MANAGER].async_remove_ban(remote_addr):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="ip_address_not_banned",
                translation_placeholders={"ip_address": str(remote_addr)},
            )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_UNBAN,
        async_unban,
        schema=probatio.Schema({probatio.Required(ATTR_IP_ADDRESS): IP_ADDRESS}),
    )
