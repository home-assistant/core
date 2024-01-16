"""Config flow to configure the BlueSound integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_UUID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_BASE_PATH, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlueSoundFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an BlueSound config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        #super().__init__(DOMAIN, "Bluesound")
        self.discovery_info: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        _LOGGER.debug(f"Bluesound zerconf discovery got host {host}")

        # Avoid probing devices that already have an entry
        self._async_abort_entries_match({CONF_HOST: host})

        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.replace(f".{zctype}", "")
        unique_id = discovery_info.properties.get("UUID")

        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
                CONF_UUID: unique_id,
            }
        )

        if unique_id:
            # If we already have the unique id, try to set it now
            # so we can avoid probing the device if its already
            # configured or ignored
            await self._async_set_unique_id_and_abort_if_already_configured(unique_id)

        self.context.update({"title_placeholders": {"name": name}})

        if not unique_id and info[CONF_UUID]:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info. Falling back to IPP UUID"
            )
            unique_id = self.discovery_info[CONF_UUID] = info[CONF_UUID]
        elif not unique_id and info[CONF_SERIAL]:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info and IPP response. Falling"
                " back to IPP serial number"
            )
            unique_id = info[CONF_SERIAL]
        elif not unique_id:
            _LOGGER.debug(
                "Unable to determine unique id from discovery info and IPP response"
            )

        if unique_id and self.unique_id != unique_id:
            await self._async_set_unique_id_and_abort_if_already_configured(unique_id)

        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_zeroconf_confirm()

    async def _async_set_unique_id_and_abort_if_already_configured(
        self, unique_id: str
    ) -> None:
        """Set the unique ID and abort if already configured."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.discovery_info[CONF_HOST],
                CONF_NAME: self.discovery_info[CONF_NAME],
            },
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

    def _show_setup_form(self, errors: dict | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=11000): int,
                }
            ),
            errors=errors or {},
        )
