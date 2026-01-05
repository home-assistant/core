"""Config flow for OpenEVSE integration."""

from typing import Any

import openevsewifi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.service_info import zeroconf

from .const import CONF_SERIAL, DOMAIN


class OpenEVSEConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Set up the instance."""
        self.discovery_info = {}

    async def check_status(self, host: str) -> bool:
        """Check if we can connect to the OpenEVSE charger."""

        charger = openevsewifi.Charger(host)
        try:
            result = await self.hass.async_add_executor_job(charger.getStatus)
        except AttributeError:
            return False
        else:
            return result is not None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = None
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            if await self.check_status(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=f"OpenEVSE {user_input[CONF_HOST]}",
                    data=user_input,
                )
            errors = {CONF_HOST: "cannot_connect"}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_import(self, data: dict[str, str]) -> ConfigFlowResult:
        """Handle the initial step."""

        self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})

        if not await self.check_status(data[CONF_HOST]):
            return self.async_abort(reason="unavailable_host")

        return self.async_create_entry(
            title=f"OpenEVSE {data[CONF_HOST]}",
            data=data,
        )

    async def _async_try_connect_and_fetch(self, host: str) -> bool:
        """Try to connect."""
        check = await self.check_status(host)
        if not check:
            raise AbortFlow("cannot_connect")
        return check

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})

        # Validate discovery entry
        if CONF_SERIAL not in discovery_info.properties:
            return self.async_abort(reason="invalid_discovery_parameters")

        host = discovery_info.host
        serial = discovery_info.properties[CONF_SERIAL]
        name = f"OpenEVSE {discovery_info.name.split('.')[0]}"
        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_NAME: name,
            }
        )
        self.context.update({"title_placeholders": {"name": name}})
        await self._async_try_connect_and_fetch(host)

        unique_id = f"{serial}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: host,
                CONF_NAME: name,
            },
        )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )
