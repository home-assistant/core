"""Config flow for SMLIGHT Zigbee integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.models import Info
from pysmlight.web import Api2
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SmlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMLIGHT Zigbee."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.client: Api2
        self.host: str | None = None
        self._reauth_entry: ConfigEntry | None = None
        self._title: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.client = Api2(self.host, session=async_get_clientsession(self.hass))
            result = await self.async_check_auth_required(user_input)
            if result.get("flow_id"):
                return result
            errors = result

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle authentication to SLZB-06 device."""
        self.context["confirm_only"] = False

        if user_input is not None and errors is None:
            result = await self.async_check_auth_required(user_input)
            if result.get("flow_id"):
                return result
            errors = result

        return self.async_show_form(
            step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Lan coordinator."""
        local_name = discovery_info.hostname[:-1]
        node_name = local_name.removesuffix(".local")

        self.host = local_name
        self.context["title_placeholders"] = {CONF_NAME: node_name}
        self.client = Api2(self.host, session=async_get_clientsession(self.hass))

        mac = discovery_info.properties.get("mac")
        # fallback for legacy firmware
        if mac is None:
            info: Info = await self.client.get_info()
            mac = info.MAC
        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured()

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_HOST] = self.host
            result = await self.async_check_auth_required(user_input)
            if result.get("flow_id"):
                return result
            errors = result

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": self.host},
            errors=errors,
        )

    async def async_check_auth_required(self, user_input: dict[str, Any]):
        """Check if auth required and redirect to auth step."""
        errors: dict[str, str] = {}
        info: Info
        step_id = None
        if self.cur_step:
            step_id = self.cur_step.get("step_id")
        try:
            if await self.client.check_auth_needed():
                if user_input.get(CONF_USERNAME) and user_input.get(CONF_PASSWORD):
                    await self.client.authenticate(
                        user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                    )
                else:
                    raise SmlightAuthError
            info = await self.client.get_info()
            await self.async_set_unique_id(format_mac(info.MAC))

        except SmlightConnectionError:
            errors["base"] = "cannot_connect"
        except SmlightAuthError:
            if step_id == "auth":
                errors["base"] = "invalid_auth"
            else:
                return await self.async_step_auth()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._abort_if_unique_id_configured()
            if user_input.get(CONF_HOST) is None:
                user_input[CONF_HOST] = self.host
            return self.async_create_entry(title=info.model, data=user_input)
        return errors

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when API Authentication failed."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self.host = entry_data[CONF_HOST]
        self.context["title_placeholders"] = {
            "host": self.host,
            "name": entry_data.get(CONF_USERNAME, "unknown"),
        }
        self.client = Api2(self.host, session=async_get_clientsession(self.hass))

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication of an existing config entry."""
        if user_input is not None:
            try:
                await self.client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except (SmlightAuthError, SmlightConnectionError):
                return self.async_abort(reason="reauth_failed")

            reauth_entry = self._reauth_entry
            assert reauth_entry is not None

            return self.async_update_reload_and_abort(
                reauth_entry, data={**user_input, CONF_HOST: self.host}
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            description_placeholders=self.context["title_placeholders"],
        )
