"""Config flow for OpenEVSE integration."""

from typing import Any

from openevsehttp.__main__ import OpenEVSE
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info import zeroconf

from .const import CONF_ID, CONF_SERIAL, DOMAIN


class OpenEVSEConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def check_status(self, host: str) -> tuple[bool, str | None]:
        """Check if we can connect to the OpenEVSE charger."""

        charger = OpenEVSE(host)
        try:
            result = await charger.test_and_get()
        except TimeoutError:
            return False, None
        return True, result.get(CONF_SERIAL)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            if (result := await self.check_status(user_input[CONF_HOST]))[0]:
                if (serial := result[1]) is not None:
                    await self.async_set_unique_id(serial, raise_on_progress=False)
                    self._abort_if_unique_id_configured()
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

        if (result := await self.check_status(data[CONF_HOST]))[0]:
            if (serial := result[1]) is not None:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
        else:
            return self.async_abort(reason="unavailable_host")

        return self.async_create_entry(
            title=f"OpenEVSE {data[CONF_HOST]}",
            data=data,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})

        await self.async_set_unique_id(discovery_info.properties[CONF_ID])
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        host = discovery_info.host
        name = f"OpenEVSE {discovery_info.name.split('.')[0]}"
        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_NAME: name,
            }
        )
        self.context.update({"title_placeholders": {"name": name}})

        if not (await self.check_status(host))[0]:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data={CONF_HOST: self.discovery_info[CONF_HOST]},
        )
