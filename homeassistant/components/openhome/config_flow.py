"""Config flow for Linn / OpenHome."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_complete_discovery(discovery_info: SsdpServiceInfo) -> bool:
    """Test if discovery is complete and usable."""
    return bool(ATTR_UPNP_UDN in discovery_info.upnp and discovery_info.ssdp_location)


class OpenhomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Openhome config flow."""

    _host: str | None
    _name: str

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        _LOGGER.debug("async_step_ssdp: started")

        if not _is_complete_discovery(discovery_info):
            _LOGGER.debug("async_step_ssdp: Incomplete discovery, ignoring")
            return self.async_abort(reason="incomplete_discovery")

        _LOGGER.debug(
            "async_step_ssdp: setting unique id %s", discovery_info.upnp[ATTR_UPNP_UDN]
        )

        await self.async_set_unique_id(discovery_info.upnp[ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.ssdp_location})

        _LOGGER.debug(
            "async_step_ssdp: create entry %s", discovery_info.upnp[ATTR_UPNP_UDN]
        )

        self._name = discovery_info.upnp[ATTR_UPNP_FRIENDLY_NAME]
        self._host = discovery_info.ssdp_location

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={CONF_HOST: self._host},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_NAME: self._name},
        )
