"""Config flow to configure LinkPlay component."""

from typing import Any

from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_bridge
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class LinkPlayConfigFlow(ConfigFlow, domain=DOMAIN):
    """LinkPlay config flow."""

    _bridge: LinkPlayBridge | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        data: dict[str, Any] = {}
        data[CONF_HOST] = host = discovery_info.host

        session = async_get_clientsession(self.hass)
        self._bridge = await linkplay_factory_bridge(host, session)

        await self.async_set_unique_id(self._bridge.device.uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["title_placeholders"] = {
            "name": self._bridge.device.name,
        }
        return await self.async_step_discovery_confirm(user_input=data)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        device_name = self._bridge.device.name if self._bridge is not None else ""
        if user_input is not None:
            return self.async_create_entry(
                title=device_name,
                data=user_input,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": device_name,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)

            self._bridge = await linkplay_factory_bridge(user_input[CONF_HOST], session)
            if self._bridge is None:
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(self._bridge.device.uuid)
            self._abort_if_unique_id_configured(updates=user_input)

            return self.async_create_entry(
                title=self._bridge.device.name,
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
