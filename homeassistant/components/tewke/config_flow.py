"""Config flow for the Tewke integration."""

from typing import TYPE_CHECKING, override

import pytewke
from pytewke.error import PyTewkeDiscoveryError

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


class TewkeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tewke."""

    VERSION = 1

    _discovered_host: str
    _discovered_name: str
    _room_name: str | None = None
    _tap: pytewke.Tap | None = None

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        unique_id = discovery_info.properties.get("hardwareId")
        if not unique_id:
            LOGGER.error("Failed to get unique ID from mDNS TXT records")
            return self.async_abort(reason="cannot_identify")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self._discovered_host = discovery_info.host
        self._discovered_name = discovery_info.properties.get(
            "name"
        ) or discovery_info.name.replace("._tewke-coap._udp.local.", "")
        self._room_name = discovery_info.properties.get("room") or None

        display_name = (
            f"{self._discovered_name} ({self._room_name})"
            if self._room_name
            else self._discovered_name
        )
        self.context["title_placeholders"] = {"name": display_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        entry = self._get_reconfigure_entry()
        self._discovered_host = entry.data[CONF_HOST]
        self._discovered_name = entry.data[CONF_NAME]
        self._room_name = entry.options.get("room_name")
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device and create the config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            tap = (
                self._tap
                if self._tap is not None
                else pytewke.Tap(self._discovered_host)
            )
            self._tap = tap

            try:
                if not tap.resources:
                    await tap.discover()

                # Verify connection by fetching scenes
                await tap.get_scenes()
            except PyTewkeDiscoveryError:
                await tap.close()
                self._tap = None
                errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_HOST: self._discovered_host,
                    CONF_NAME: self._discovered_name,
                }
                options = {"room_name": self._room_name} if self._room_name else {}

                if self.source == SOURCE_RECONFIGURE:
                    entry = self._get_reconfigure_entry()
                    # Do not override existing options unless needed, wait,
                    # actually during reconfigure, maybe keep old options?
                    # The old code did: `options = dict(entry.options)`
                    # Let's keep that.

                    await tap.close()
                    self._tap = None

                    return self.async_update_reload_and_abort(
                        entry,
                        data=data,
                        options=dict(entry.options),
                    )

                await tap.close()
                self._tap = None

                return self.async_create_entry(
                    title=self._discovered_name,
                    data=data,
                    options=options,
                )

        room_suffix = f", in room **{self._room_name}**" if self._room_name else ""
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_name,
                "room_suffix": room_suffix,
            },
            errors=errors,
        )
