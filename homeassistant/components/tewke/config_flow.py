"""Config flow for the Tewke integration."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override

import pytewke
from pytewke.error import PyTewkeDiscoveryError

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from pytewke.data import Scene

    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


class TewkeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tewke."""

    VERSION = 1

    _discovered_host: str
    _discovered_name: str
    _room_name: str | None = None
    _scenes: dict[str, Scene]
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tewke Tap Panel."""
        self._discovered_host = entry_data[CONF_HOST]
        self._discovered_name = entry_data[CONF_NAME]
        self._room_name = entry_data.get("room_name")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_confirmation(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        entry = self._get_reconfigure_entry()
        self._discovered_host = entry.data[CONF_HOST]
        self._discovered_name = entry.data[CONF_NAME]
        self._room_name = entry.data.get("room_name")
        return await self.async_step_confirmation()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device and proceed to scene setup."""
        if user_input is not None:
            return await self.async_step_confirmation()

        room_suffix = f", in room **{self._room_name}**" if self._room_name else ""
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_name,
                "room_suffix": room_suffix,
            },
        )

    async def async_step_confirmation(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation before creating the config entry."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="confirmation",
                description_placeholders={"name": self._discovered_name},
                errors=errors,
            )

        tap = self._tap if self._tap is not None else pytewke.Tap(self._discovered_host)
        self._tap = tap

        try:
            if not tap.resources:
                await tap.discover()

            scenes = await tap.get_scenes()
        except PyTewkeDiscoveryError:
            await tap.close()
            self._tap = None
            errors["base"] = "cannot_connect"
        else:
            self._scenes = scenes
            LOGGER.debug("Discovered scenes: %s", scenes)

            data = {
                CONF_HOST: self._discovered_host,
                CONF_NAME: self._discovered_name,
                "room_name": self._room_name,
                "scenes": self._scenes,
            }

            if self.source == SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
                options = dict(entry.options)

                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    options=options,
                )

            if self.source == SOURCE_REAUTH:
                entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                )

            return self.async_create_entry(
                title=self._discovered_name,
                data=data,
            )

        return self.async_show_form(
            step_id="confirmation",
            description_placeholders={"name": self._discovered_name},
            errors=errors,
        )
