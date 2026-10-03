"""Config flow for the LibreSync integration."""

from typing import Any, override
from urllib.parse import urlparse

from aiolibresync import DiscoveredDevice, async_probe, async_probe_control
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import DEFAULT_NAME, DOMAIN

STEP_USER_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


class LibreSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for LibreSync. A hub is identified by its UPnP UDN."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered: DiscoveredDevice | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a hub added by address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            device = await async_probe(host)
            if device is None:
                errors["base"] = "cannot_connect"
            elif not device.udn:
                errors["base"] = "no_identity"
            else:
                await self.async_set_unique_id(device.udn, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=device.name or DEFAULT_NAME, data={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a hub found by SSDP."""
        udn = discovery_info.upnp.get(ATTR_UPNP_UDN)
        host = urlparse(discovery_info.ssdp_location or "").hostname
        if not udn or not host:
            return self.async_abort(reason="cannot_connect")

        # A known or ignored hub stops here, before anything is sent to it.
        await self.async_set_unique_id(udn)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        if not await async_probe_control(host):
            return self.async_abort(reason="cannot_connect")

        self._discovered = DiscoveredDevice(
            host=host, udn=udn, name=discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
        )
        self.context["title_placeholders"] = {
            "name": self._discovered.name or DEFAULT_NAME
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered hub."""
        assert self._discovered is not None
        name = self._discovered.name or DEFAULT_NAME
        if user_input is not None:
            return self.async_create_entry(
                title=name, data={CONF_HOST: self._discovered.host}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": name}
        )
