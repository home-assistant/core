"""Config flow for HDFury Integration."""

from typing import Any

from hdfury import HDFuryAPI, HDFuryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN


class HDFuryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Config Flow for HDFury."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host

        serial = await self._validate_connection(host)
        if serial is not None:
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            self.context["title_placeholders"] = {
                CONF_HOST: self.data[CONF_HOST],
            }

            return await self.async_step_discovery_confirm()

        return self.async_abort(reason="cannot_connect")

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"HDFury ({self.data[CONF_HOST]})",
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_HOST: self.data[CONF_HOST],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Initial Setup."""

        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            serial = await self._validate_connection(host)
            if serial is not None:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"HDFury ({host})", data=user_input
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]

            serial = await self._validate_connection(host)
            if serial is not None:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch(reason="incorrect_device")
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data.get(CONF_HOST),
                    ): str
                }
            ),
            description_placeholders={
                "title": reconfigure_entry.title,
            },
            errors=errors,
        )

    async def _validate_connection(self, host: str) -> str | None:
        """Try to fetch serial number to confirm it's a valid HDFury device."""

        client = HDFuryAPI(host, async_get_clientsession(self.hass))

        try:
            data = await client.get_board()
        except HDFuryError:
            return None

        return data["serial"]
