"""Config flow for Cambridge Audio."""

from typing import Any

from aiostreammagic import StreamMagicClient, StreamMagicError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Cambridge Audio configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.client: StreamMagicClient | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        self.data[CONF_MODEL] = discovery_info.properties["model"]

        await self.async_set_unique_id(discovery_info.properties["serial"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        session = async_get_clientsession(self.hass)
        self.client = StreamMagicClient(host, session=session)
        await self.client.get_info()

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
        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = StreamMagicClient(host, session)
            try:
                info = await client.get_info()
            except StreamMagicError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.udn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name,
                    data={CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
