"""Config flow for the Duco integration."""

from __future__ import annotations

import logging
from typing import Any

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class DucoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Duco."""

    VERSION = 1
    MINOR_VERSION = 1

    _host: str
    _box_name: str

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        try:
            box_name, mac = await self._validate_input(discovery_info.host)
        except DucoConnectionError:
            return self.async_abort(reason="cannot_connect")
        except DucoError:
            _LOGGER.exception("Unexpected error discovering Duco box via zeroconf")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self._host = discovery_info.host
        self._box_name = box_name
        self.context["title_placeholders"] = {"name": box_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._box_name,
                data={CONF_HOST: self._host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._box_name},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                box_name, mac = await self._validate_input(user_input[CONF_HOST])
            except DucoConnectionError:
                errors["base"] = "cannot_connect"
            except DucoError:
                _LOGGER.exception("Unexpected error connecting to Duco box")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=box_name,
                    data_updates={CONF_HOST: user_input[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                box_name, mac = await self._validate_input(user_input[CONF_HOST])
            except DucoConnectionError:
                errors["base"] = "cannot_connect"
            except DucoError:
                _LOGGER.exception("Unexpected error connecting to Duco box")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(mac), raise_on_progress=False)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=box_name,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _validate_input(self, host: str) -> tuple[str, str]:
        """Validate the user input by connecting to the Duco box.

        Returns a tuple of (box_name, mac_address).
        """
        client = DucoClient(
            session=async_get_clientsession(self.hass),
            host=host,
        )
        board_info = await client.async_get_board_info()
        lan_info = await client.async_get_lan_info()
        return board_info.box_name, lan_info.mac
