"""Config flow for LG webOS TV integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self
from urllib.parse import urlparse

from aiowebostv import WebOsClient, WebOsTvPairError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from . import WebOsTvConfigEntry
from .const import CONF_SOURCES, DEFAULT_NAME, DOMAIN, WEBOSTV_EXCEPTIONS
from .helpers import get_sources

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_control_connect(
    hass: HomeAssistant, host: str, key: str | None
) -> WebOsClient:
    """Create LG webOS client and connect to the TV."""
    client = WebOsClient(
        host,
        key,
        client_session=async_get_clientsession(hass),
    )

    await client.connect()

    return client


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """LG webOS TV configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize workflow."""
        self._host: str = ""
        self._name: str = ""
        self._uuid: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: WebOsTvConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self.async_step_pairing()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display pairing form."""
        self._async_abort_entries_match({CONF_HOST: self._host})

        self.context["title_placeholders"] = {"name": self._name}
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = await async_control_connect(self.hass, self._host, None)
            except WebOsTvPairError:
                errors["base"] = "error_pairing"
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    client.tv_info.hello["deviceUUID"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured({CONF_HOST: self._host})
                data = {CONF_HOST: self._host, CONF_CLIENT_SECRET: client.client_key}

                if not self._name:
                    self._name = f"{DEFAULT_NAME} {client.tv_info.system['modelName']}"
                return self.async_create_entry(title=self._name, data=data)

        return self.async_show_form(step_id="pairing", errors=errors)

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        assert discovery_info.ssdp_location
        host = urlparse(discovery_info.ssdp_location).hostname
        assert host
        self._host = host
        self._name = discovery_info.upnp.get(
            ATTR_UPNP_FRIENDLY_NAME, DEFAULT_NAME
        ).replace("[LG]", "LG")

        uuid = discovery_info.upnp[ATTR_UPNP_UDN]
        assert uuid
        uuid = uuid.removeprefix("uuid:")
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured({CONF_HOST: self._host})

        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        self._uuid = uuid
        return await self.async_step_pairing()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return other_flow._host == self._host  # noqa: SLF001

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an WebOsTvPairError."""
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = await async_control_connect(self.hass, self._host, None)
            except WebOsTvPairError:
                errors["base"] = "error_pairing"
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                reauth_entry = self._get_reauth_entry()
                data = {CONF_HOST: self._host, CONF_CLIENT_SECRET: client.client_key}
                return self.async_update_reload_and_abort(reauth_entry, data=data)

        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            client_key = reconfigure_entry.data.get(CONF_CLIENT_SECRET)

            try:
                client = await async_control_connect(self.hass, host, client_key)
            except WebOsTvPairError:
                errors["base"] = "error_pairing"
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(client.tv_info.hello["deviceUUID"])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
                return self.async_update_reload_and_abort(reconfigure_entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST)
                    ): cv.string
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: WebOsTvConfigEntry) -> None:
        """Initialize options flow."""
        self.host = config_entry.data[CONF_HOST]
        self.key = config_entry.data[CONF_CLIENT_SECRET]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            options_input = {CONF_SOURCES: user_input[CONF_SOURCES]}
            return self.async_create_entry(title="", data=options_input)
        # Get sources
        sources_list = []
        try:
            client = await async_control_connect(self.hass, self.host, self.key)
            sources_list = get_sources(client.tv_state)
        except WebOsTvPairError:
            errors["base"] = "error_pairing"
        except WEBOSTV_EXCEPTIONS:
            errors["base"] = "cannot_connect"

        option_sources = self.config_entry.options.get(CONF_SOURCES, [])
        sources = [s for s in option_sources if s in sources_list]
        if not sources:
            sources = sources_list

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SOURCES,
                    description={"suggested_value": sources},
                ): cv.multi_select({source: source for source in sources_list}),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
