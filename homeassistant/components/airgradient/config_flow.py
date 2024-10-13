"""Config flow for Airgradient."""

from typing import Any

from airgradient import (
    AirGradientClient,
    AirGradientError,
    AirGradientParseError,
    ConfigurationControl,
)
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

MIN_VERSION = AwesomeVersion("3.1.1")


class AirGradientConfigFlow(ConfigFlow, domain=DOMAIN):
    """AirGradient config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.client: AirGradientClient | None = None

    async def set_configuration_source(self) -> None:
        """Set configuration source to local if it hasn't been set yet."""
        assert self.client
        config = await self.client.get_config()
        if config.configuration_control is ConfigurationControl.NOT_INITIALIZED:
            await self.client.set_configuration_control(ConfigurationControl.LOCAL)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host
        self.data[CONF_MODEL] = discovery_info.properties["model"]

        await self.async_set_unique_id(discovery_info.properties["serialno"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        if AwesomeVersion(discovery_info.properties["fw_ver"]) < MIN_VERSION:
            return self.async_abort(reason="invalid_version")

        session = async_get_clientsession(self.hass)
        self.client = AirGradientClient(host, session=session)
        await self.client.get_current_measures()

        self.context["title_placeholders"] = {
            "model": self.data[CONF_MODEL],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            await self.set_configuration_source()
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
            self.client = AirGradientClient(user_input[CONF_HOST], session=session)
            try:
                current_measures = await self.client.get_current_measures()
            except AirGradientParseError:
                return self.async_abort(reason="invalid_version")
            except AirGradientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    current_measures.serial_number, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                await self.set_configuration_source()
                return self.async_create_entry(
                    title=current_measures.model,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
