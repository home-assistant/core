"""Config flow for Bose SoundTouch integration."""

import logging
from typing import Any

from libsoundtouch import soundtouch_device
from requests import RequestException
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SoundtouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bose SoundTouch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new SoundTouch config flow."""
        self.host: str | None = None
        self.name = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]

            try:
                await self._async_get_device_id(raise_on_progress=False)
            except RequestException:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_create_soundtouch_entry()

        return self.async_show_form(
            step_id="user",
            last_step=True,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by a zeroconf discovery."""
        self.host = discovery_info.host

        try:
            await self._async_get_device_id()
        except RequestException:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": self.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_create_soundtouch_entry()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            last_step=True,
            description_placeholders={"name": self.name},
        )

    async def _async_get_device_id(self, raise_on_progress: bool = True) -> None:
        """Get device ID from SoundTouch device."""
        device = await self.hass.async_add_executor_job(soundtouch_device, self.host)

        # Check if already configured
        await self.async_set_unique_id(
            device.config.device_id, raise_on_progress=raise_on_progress
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})

        self.name = device.config.name

    async def _async_create_soundtouch_entry(self):
        """Finish config flow and create a SoundTouch config entry."""
        return self.async_create_entry(
            title=self.name,
            data={
                CONF_HOST: self.host,
            },
        )
