"""Config flow for Airgradient."""

from typing import Any

from airgradient import AirGradientClient, AirGradientError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class AirGradientConfigFlow(ConfigFlow, domain=DOMAIN):
    """AirGradient config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host
        self.data[CONF_MODEL] = discovery_info.properties["model"]

        await self.async_set_unique_id(discovery_info.properties["serialno"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        session = async_get_clientsession(self.hass)
        air_gradient = AirGradientClient(host, session=session)
        await air_gradient.get_current_measures()

        self.context["title_placeholders"] = {
            "model": self.data[CONF_MODEL],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data[CONF_MODEL],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.data[CONF_MODEL],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            air_gradient = AirGradientClient(user_input[CONF_HOST], session=session)
            try:
                current_measures = await air_gradient.get_current_measures()
            except AirGradientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(current_measures.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=current_measures.model,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
