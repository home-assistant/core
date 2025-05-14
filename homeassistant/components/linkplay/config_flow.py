"""Config flow to configure LinkPlay component."""

import logging
from typing import Any

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_httpapi_bridge
from linkplay.exceptions import LinkPlayRequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .utils import async_get_client_session

_LOGGER = logging.getLogger(__name__)


class LinkPlayConfigFlow(ConfigFlow, domain=DOMAIN):
    """LinkPlay config flow."""

    def __init__(self) -> None:
        """Initialize the LinkPlay config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""

        session: ClientSession = await async_get_client_session(self.hass)
        bridge: LinkPlayBridge | None = None

        try:
            bridge = await linkplay_factory_httpapi_bridge(discovery_info.host, session)
        except LinkPlayRequestException:
            _LOGGER.exception(
                "Failed to connect to LinkPlay device at %s", discovery_info.host
            )
            return self.async_abort(reason="cannot_connect")

        self.data[CONF_HOST] = discovery_info.host
        self.data[CONF_MODEL] = bridge.device.name

        await self.async_set_unique_id(bridge.device.uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context["title_placeholders"] = {
            "name": self.data[CONF_MODEL],
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
                "name": self.data[CONF_MODEL],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session: ClientSession = await async_get_client_session(self.hass)
            bridge: LinkPlayBridge | None = None

            try:
                bridge = await linkplay_factory_httpapi_bridge(
                    user_input[CONF_HOST], session
                )
            except LinkPlayRequestException:
                _LOGGER.exception(
                    "Failed to connect to LinkPlay device at %s", user_input[CONF_HOST]
                )
                errors["base"] = "cannot_connect"

            if bridge is not None:
                self.data[CONF_HOST] = user_input[CONF_HOST]
                self.data[CONF_MODEL] = bridge.device.name

                await self.async_set_unique_id(
                    bridge.device.uuid, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self.data[CONF_HOST]}
                )

                return self.async_create_entry(
                    title=self.data[CONF_MODEL],
                    data={CONF_HOST: self.data[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
