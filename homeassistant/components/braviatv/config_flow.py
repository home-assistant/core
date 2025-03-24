"""Config flow to configure the Bravia TV integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

from aiohttp import CookieJar
from pybravia import BraviaAuthError, BraviaClient, BraviaError, BraviaNotSupported
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PIN
from homeassistant.helpers import instance_id
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)
from homeassistant.util.network import is_host_valid

from .const import (
    ATTR_CID,
    ATTR_MAC,
    ATTR_MODEL,
    CONF_NICKNAME,
    CONF_USE_PSK,
    DOMAIN,
    NICKNAME_PREFIX,
)


class BraviaTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bravia TV integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.client: BraviaClient | None = None
        self.device_config: dict[str, Any] = {}

    def create_client(self) -> None:
        """Create Bravia TV client from config."""
        host = self.device_config[CONF_HOST]
        session = async_create_clientsession(
            self.hass,
            cookie_jar=CookieJar(unsafe=True, quote_cookie=False),
        )
        self.client = BraviaClient(host=host, session=session)

    async def gen_instance_ids(self) -> tuple[str, str]:
        """Generate client_id and nickname."""
        uuid = await instance_id.async_get(self.hass)
        return uuid, f"{NICKNAME_PREFIX} {uuid[:6]}"

    async def async_connect_device(self) -> None:
        """Connect to Bravia TV device from config."""
        assert self.client

        pin = self.device_config[CONF_PIN]
        use_psk = self.device_config[CONF_USE_PSK]

        if use_psk:
            await self.client.connect(psk=pin)
        else:
            client_id = self.device_config[CONF_CLIENT_ID]
            nickname = self.device_config[CONF_NICKNAME]
            await self.client.connect(pin=pin, clientid=client_id, nickname=nickname)
        await self.client.set_wol_mode(True)

    async def async_create_device(self) -> ConfigFlowResult:
        """Create Bravia TV device from config."""
        assert self.client
        await self.async_connect_device()

        system_info = await self.client.get_system_info()
        cid = system_info[ATTR_CID].lower()
        title = system_info[ATTR_MODEL]

        self.device_config[CONF_MAC] = system_info[ATTR_MAC]

        await self.async_set_unique_id(cid)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=self.device_config)

    async def async_reauth_device(self) -> ConfigFlowResult:
        """Reauthorize Bravia TV device from config."""
        assert self.client
        await self.async_connect_device()

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), data=self.device_config
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if is_host_valid(host):
                self.device_config[CONF_HOST] = host
                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authorize step."""
        self.create_client()

        if user_input is not None:
            self.device_config[CONF_USE_PSK] = user_input[CONF_USE_PSK]
            if user_input[CONF_USE_PSK]:
                return await self.async_step_psk()
            return await self.async_step_pin()

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USE_PSK, default=False): bool,
                }
            ),
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle PIN authorize step."""
        errors: dict[str, str] = {}
        client_id, nickname = await self.gen_instance_ids()

        if user_input is not None:
            self.device_config[CONF_PIN] = user_input[CONF_PIN]
            self.device_config[CONF_CLIENT_ID] = client_id
            self.device_config[CONF_NICKNAME] = nickname
            try:
                if self.source == SOURCE_REAUTH:
                    return await self.async_reauth_device()
                return await self.async_create_device()
            except BraviaAuthError:
                errors["base"] = "invalid_auth"
            except BraviaNotSupported:
                errors["base"] = "unsupported_model"
            except BraviaError:
                errors["base"] = "cannot_connect"

        assert self.client

        try:
            await self.client.pair(client_id, nickname)
        except BraviaError:
            return self.async_abort(reason="no_ip_control")

        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_psk(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle PSK authorize step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.device_config[CONF_PIN] = user_input[CONF_PIN]
            try:
                if self.source == SOURCE_REAUTH:
                    return await self.async_reauth_device()
                return await self.async_create_device()
            except BraviaAuthError:
                errors["base"] = "invalid_auth"
            except BraviaNotSupported:
                errors["base"] = "unsupported_model"
            except BraviaError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="psk",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered device."""
        # We can cast the hostname to str because the ssdp_location is not bytes and
        # not a relative url
        host = cast(str, urlparse(discovery_info.ssdp_location).hostname)

        await self.async_set_unique_id(discovery_info.upnp[ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})

        scalarweb_info = discovery_info.upnp["X_ScalarWebAPI_DeviceInfo"]
        service_types = scalarweb_info["X_ScalarWebAPI_ServiceList"][
            "X_ScalarWebAPI_ServiceType"
        ]

        if "videoScreen" not in service_types:
            return self.async_abort(reason="not_bravia_device")

        model_name = discovery_info.upnp[ATTR_UPNP_MODEL_NAME]
        friendly_name = discovery_info.upnp[ATTR_UPNP_FRIENDLY_NAME]

        self.context["title_placeholders"] = {
            CONF_NAME: f"{model_name} ({friendly_name})",
            CONF_HOST: host,
        }

        self.device_config[CONF_HOST] = host
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return await self.async_step_authorize()

        return self.async_show_form(step_id="confirm")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.device_config = {**entry_data}
        return await self.async_step_authorize()
