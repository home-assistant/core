"""Config flow to configure the Bravia TV integration."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aiohttp import CookieJar
from pybravia import BraviaTV, BraviaTVAuthError, BraviaTVError, BraviaTVNotSupported
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PIN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util.network import is_host_valid

from . import BraviaTVCoordinator
from .const import (
    ATTR_CID,
    ATTR_MAC,
    ATTR_MODEL,
    CLIENTID_PREFIX,
    CONF_IGNORED_SOURCES,
    CONF_USE_PSK,
    DOMAIN,
    NICKNAME,
)


class BraviaTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bravia TV integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.client: BraviaTV | None = None
        self.device_config: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BraviaTVOptionsFlowHandler:
        """Bravia TV options callback."""
        return BraviaTVOptionsFlowHandler(config_entry)

    def create_client(self) -> None:
        """Create Bravia TV client from config."""
        host = self.device_config[CONF_HOST]
        session = async_create_clientsession(
            self.hass,
            cookie_jar=CookieJar(unsafe=True, quote_cookie=False),
        )
        self.client = BraviaTV(host=host, session=session)

    async def async_create_device(self) -> FlowResult:
        """Initialize and create Bravia TV device from config."""
        assert self.client

        pin = self.device_config[CONF_PIN]
        use_psk = self.device_config[CONF_USE_PSK]

        if use_psk:
            await self.client.connect(psk=pin)
        else:
            await self.client.connect(
                pin=pin, clientid=CLIENTID_PREFIX, nickname=NICKNAME
            )
        await self.client.set_wol_mode(True)

        system_info = await self.client.get_system_info()
        cid = system_info[ATTR_CID].lower()
        title = system_info[ATTR_MODEL]

        self.device_config[CONF_MAC] = system_info[ATTR_MAC]

        await self.async_set_unique_id(cid)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=self.device_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if is_host_valid(host):
                self.device_config[CONF_HOST] = host
                self.create_client()
                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Authorize Bravia TV device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.device_config[CONF_PIN] = user_input[CONF_PIN]
            self.device_config[CONF_USE_PSK] = user_input[CONF_USE_PSK]
            try:
                return await self.async_create_device()
            except BraviaTVAuthError:
                errors["base"] = "invalid_auth"
            except BraviaTVNotSupported:
                errors["base"] = "unsupported_model"
            except BraviaTVError:
                errors["base"] = "cannot_connect"

        assert self.client

        try:
            await self.client.pair(CLIENTID_PREFIX, NICKNAME)
        except BraviaTVError:
            return self.async_abort(reason="no_ip_control")

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN, default=""): str,
                    vol.Required(CONF_USE_PSK, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a discovered device."""
        parsed_url = urlparse(discovery_info.ssdp_location)
        host = parsed_url.hostname

        await self.async_set_unique_id(discovery_info.upnp[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})

        scalarweb_info = discovery_info.upnp["X_ScalarWebAPI_DeviceInfo"]
        service_types = scalarweb_info["X_ScalarWebAPI_ServiceList"][
            "X_ScalarWebAPI_ServiceType"
        ]

        if "videoScreen" not in service_types:
            return self.async_abort(reason="not_bravia_device")

        model_name = discovery_info.upnp[ssdp.ATTR_UPNP_MODEL_NAME]
        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]

        self.context["title_placeholders"] = {
            CONF_NAME: f"{model_name} ({friendly_name})",
            CONF_HOST: host,
        }

        self.device_config[CONF_HOST] = host
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            self.create_client()
            return await self.async_step_authorize()

        return self.async_show_form(step_id="confirm")


class BraviaTVOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Bravia TV."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Bravia TV options flow."""
        self.config_entry = config_entry
        self.ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES)
        self.source_list: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        coordinator: BraviaTVCoordinator = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]

        await coordinator.async_update_sources()
        sources = coordinator.source_map.values()
        self.source_list = [item["title"] for item in sources]
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORED_SOURCES, default=self.ignored_sources
                    ): cv.multi_select(self.source_list)
                }
            ),
        )
