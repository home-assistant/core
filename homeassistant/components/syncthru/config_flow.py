"""Config flow for Samsung SyncThru."""

from typing import Any, cast
from urllib.parse import urlparse

from pysyncthru import ConnectionMode, SyncThru, SyncThruAPINotSupported
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL, CONF_NAME, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_PRESENTATION_URL,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from .const import DOMAIN


class SyncThruConfigFlow(ConfigFlow, domain=DOMAIN):
    """Samsung SyncThru config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    url: str
    model: str
    hostname: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        errors = {}
        if user_input is not None:
            printer = SyncThru(
                user_input[CONF_URL],
                async_get_clientsession(self.hass),
                connection_mode=ConnectionMode.API,
            )
            try:
                await printer.update()
            except SyncThruAPINotSupported:
                return self.async_abort(reason="syncthru_not_supported")
            if printer.is_unknown_state():
                errors["base"] = "unknown_state"
            else:
                await self.async_set_unique_id(
                    printer.serial_number(), raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=cast(str, printer.hostname()), data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP initiated flow."""

        self.url = discovery_info.upnp.get(
            ATTR_UPNP_PRESENTATION_URL,
            f"http://{urlparse(discovery_info.ssdp_location or '').hostname}/",
        )
        await self.async_set_unique_id(discovery_info.upnp[ATTR_UPNP_SERIAL])
        self._abort_if_unique_id_configured(updates={CONF_URL: self.url})

        printer = SyncThru(
            self.url,
            async_get_clientsession(self.hass),
            connection_mode=ConnectionMode.API,
        )
        try:
            await printer.update()
        except SyncThruAPINotSupported:
            return self.async_abort(reason="syncthru_not_supported")
        if printer.is_unknown_state():
            return self.async_abort(reason="unknown_state")

        self.model = cast(str, printer.model())
        self.hostname = cast(str, printer.hostname())
        self.context["title_placeholders"] = {
            CONF_MODEL: self.model,
            CONF_NAME: self.hostname,
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation by user."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.hostname, data={CONF_URL: self.url}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_MODEL: self.model, CONF_NAME: self.hostname},
        )
