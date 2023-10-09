"""Config flow for Wyoming integration."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .data import WyomingService

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wyoming integration."""

    VERSION = 1

    _hassio_discovery: HassioServiceInfo

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        service = await WyomingService.create(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
        )

        if service is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        # ASR = automated speech recognition (speech-to-text)
        asr_installed = [asr for asr in service.info.asr if asr.installed]

        # TTS = text-to-speech
        tts_installed = [tts for tts in service.info.tts if tts.installed]

        # wake-word-detection
        wake_installed = [wake for wake in service.info.wake if wake.installed]

        if asr_installed:
            name = asr_installed[0].name
        elif tts_installed:
            name = tts_installed[0].name
        elif wake_installed:
            name = wake_installed[0].name
        else:
            return self.async_abort(reason="no_services")

        return self.async_create_entry(title=name, data=user_input)

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle Supervisor add-on discovery."""
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured()

        self._hassio_discovery = discovery_info
        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name},
                "configuration_url": f"homeassistant://hassio/addon/{discovery_info.slug}/info",
            }
        )
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Supervisor discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uri = urlparse(self._hassio_discovery.config["uri"])
            if service := await WyomingService.create(uri.hostname, uri.port):
                if (
                    not any(asr for asr in service.info.asr if asr.installed)
                    and not any(tts for tts in service.info.tts if tts.installed)
                    and not any(wake for wake in service.info.wake if wake.installed)
                ):
                    return self.async_abort(reason="no_services")

                return self.async_create_entry(
                    title=self._hassio_discovery.name,
                    data={CONF_HOST: uri.hostname, CONF_PORT: uri.port},
                )

            errors = {"base": "cannot_connect"}

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery.name},
            errors=errors,
        )
