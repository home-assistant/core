"""Config flow for Ruckus integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import operator
from typing import Any

from aioruckus import AjaxSession, SystemStat
from aioruckus.exceptions import AuthenticationError, SchemaError
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    API_CLIENT_HOSTNAME,
    API_MESH_NAME,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_SERIAL,
    CONF_MAC_FILTER,
    DOMAIN,
    KEY_SYS_CLIENTS,
    KEY_SYS_SERIAL,
    KEY_SYS_TITLE,
)

_LOGGER = logging.getLogger(__package__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        async with AjaxSession.async_create(
            data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD]
        ) as ruckus:
            mesh_info = await ruckus.api.get_mesh_info()
            system_info = await ruckus.api.get_system_info(SystemStat.SYSINFO)
    except AuthenticationError as autherr:
        raise InvalidAuth from autherr
    except (ConnectionError, SchemaError) as connerr:
        raise CannotConnect from connerr

    mesh_name = mesh_info[API_MESH_NAME]
    zd_serial = system_info[API_SYS_SYSINFO][API_SYS_SYSINFO_SERIAL]

    return {
        KEY_SYS_TITLE: mesh_name,
        KEY_SYS_SERIAL: zd_serial,
    }


class RuckusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruckus."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RuckusOptionsFlowHandler:
        """Get the options flow for this handler."""
        return RuckusOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[KEY_SYS_SERIAL])
                if self.source != SOURCE_REAUTH:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info[KEY_SYS_TITLE], data=user_input
                    )
                self._abort_if_unique_id_mismatch(reason="invalid_host")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data=user_input
                )

        data_schema = DATA_SCHEMA
        if self.source == SOURCE_REAUTH:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self._get_reauth_entry().data
            )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_user()


class RuckusOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Ruckus options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            new_filter: list[str] = user_input.get(CONF_MAC_FILTER, [])

            # Remove entities for devices no longer in the allow-list
            if new_filter:
                entity_registry = er.async_get(self.hass)
                for reg_entry in er.async_entries_for_config_entry(
                    entity_registry, self.config_entry.entry_id
                ):
                    if (
                        reg_entry.domain == DEVICE_TRACKER_DOMAIN
                        and reg_entry.unique_id not in new_filter
                    ):
                        entity_registry.async_remove(reg_entry.entity_id)

            return self.async_create_entry(data={CONF_MAC_FILTER: new_filter})

        coordinator = self.config_entry.runtime_data
        current_filter: list[str] = self.config_entry.options.get(CONF_MAC_FILTER, [])

        # Build client dict from active clients
        clients: dict[str, str] = {
            mac: f"{client[API_CLIENT_HOSTNAME]} ({mac})"
            for mac, client in coordinator.data[KEY_SYS_CLIENTS].items()
        }

        # Preserve previously selected but now-offline clients
        clients |= {
            mac: f"Unknown ({mac})" for mac in current_filter if mac not in clients
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAC_FILTER,
                        default=current_filter,
                    ): cv.multi_select(
                        dict(sorted(clients.items(), key=operator.itemgetter(1)))
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
