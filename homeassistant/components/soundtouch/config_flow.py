"""Config flow for Bose SoundTouch integration."""

from __future__ import annotations

from functools import partial
from typing import Any

import defusedxml.ElementTree as ET
from libsoundtouch import soundtouch_device
import requests
from requests import RequestException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_SOURCE_ALIASES, DOMAIN


class SoundtouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bose SoundTouch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new SoundTouch config flow."""
        self.host: str | None = None
        self.name: str | None = None

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

        if self.name:
            # If we have a name, use it as flow title
            self.context["title_placeholders"] = {"name": self.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_create_soundtouch_entry()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            last_step=True,
            description_placeholders={"name": self.name or "?"},
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

    async def _async_create_soundtouch_entry(self) -> ConfigFlowResult:
        """Finish config flow and create a SoundTouch config entry."""
        return self.async_create_entry(
            title=self.name or "SoundTouch",
            data={
                CONF_HOST: self.host,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SoundtouchOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SoundtouchOptionsFlowHandler(config_entry)


class SoundtouchOptionsFlowHandler(OptionsFlow):
    """Handle SoundTouch options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize SoundTouch options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the SoundTouch options."""
        # Let's try to fetch sources if the device is reachable
        host = self._config_entry.data[CONF_HOST]
        sources = []
        try:
            # We can't easily call _update_sources here as it's in the media_player
            # but we can do a quick check
            url = f"http://{host}:8090/sources"
            response = await self.hass.async_add_executor_job(
                partial(requests.get, url, timeout=5)
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for source_item in root.findall("sourceItem"):
                if source_item.get("status") == "READY":
                    s_type = source_item.get("source")
                    s_acc = source_item.get("sourceAccount")
                    sources.append(s_acc if s_type == "PRODUCT" else s_type)
        except (requests.RequestException, ET.ParseError):
            # Fallback to some common ones if fetch fails
            sources = ["HDMI_1", "HDMI_2", "HDMI_3", "TV", "AUX", "BLUETOOTH"]

        current_aliases = self._config_entry.options.get(CONF_SOURCE_ALIASES, {})

        if user_input is not None:
            # Convert flat fields back to dict
            new_aliases = {}
            for source in sources:
                val = user_input.get(f"alias_{source}")
                if val and val.strip():
                    new_aliases[source] = val
            return self.async_create_entry(
                title="", data={CONF_SOURCE_ALIASES: new_aliases}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        f"alias_{source}",
                        default=current_aliases.get(source, ""),
                    ): str
                    for source in sources
                }
            ),
        )
