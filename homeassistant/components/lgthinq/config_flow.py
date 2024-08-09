# SPDX-FileCopyrightText: Copyright 2024 LG Electronics Inc.
# SPDX-License-Identifier: LicenseRef-LGE-Proprietary

"""Config flow for LG ThinQ."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from urllib.parse import urlparse

import pycountry
import voluptuous as vol
from aiowebostv import WebOsTvPairError
from async_upnp_client.const import AddressTupleVXType
from async_upnp_client.ssdp_listener import SsdpSearchListener
from async_upnp_client.utils import CaseInsensitiveDict
from nmap import PortScanner, PortScannerError
from thinqconnect.thinq_api import ThinQApi, ThinQApiResponse

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_SECRET,
    CONF_COUNTRY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import async_control_connect
from .const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_SOUNDBAR,
    CONF_ENTRY_TYPE_THINQ,
    CONF_ENTRY_TYPE_WEBOSTV,
    CONF_SOUNDBAR_MODEL,
    CONF_SOURCES,
    DEFAULT_COUNTRY,
    DOMAIN,
    GUIDE_ENTER_TV_IP,
    IPV4_BROADCAST,
    SOUNDBAR_DEFAULT_NAME,
    SSDP_MX,
    THINQ_DEFAULT_NAME,
    THINQ_PAT_URL,
    TRANSLATION_ERROR_CODE,
    WEBOS_DEFAULT_NAME,
    WEBOS_SECOND_SCREEN_ST,
    WEBOSTV_EXCEPTIONS,
)
from .helpers import async_get_sources, get_conf_sources
from .soundbar_client import SOUNDBAR_PORT, config_connect, config_device

_LOGGER = logging.getLogger(__name__)

SUPPORTED_COUNTRIES = [
    SelectOptionDict(value=x.alpha_2, label=x.name)
    for x in pycountry.countries
]


class ThinQFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the ThinQ integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._country: str | None = None
        self._access_token: str | None = None
        self._entity_name: str | None = None
        self._host: str = ""
        self._name: str = ""
        self._uuid: str | None = None
        self._entry: ConfigEntry | None = None
        self._soundbar_host: str = ""

    def _get_default_country_code(self) -> str:
        """Get default country code based on Home Assistant config."""
        country = self.hass.config.country
        if country is not None:
            for x in SUPPORTED_COUNTRIES:
                if x.get("value") == country:
                    return country
        return DEFAULT_COUNTRY

    async def _validate_and_create_entry(self) -> ConfigFlowResult:
        """Create an entry for the flow."""
        connect_client_id: str = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"

        # validate PAT
        api = ThinQApi(
            session=async_get_clientsession(self.hass),
            access_token=self._access_token,
            country_code=self._country,
            client_id=connect_client_id,
        )
        result: ThinQApiResponse = await api.async_get_device_list()
        _LOGGER.debug("validate_and_create_entry: %s", result)

        if result.status >= 400:
            # support translation for TRANSLATION_ERROR_CODE, key is error_code
            reason_str: str = (
                result.error_code
                if result.error_code in TRANSLATION_ERROR_CODE
                else result.error_message
            )
            return self.async_abort(reason=reason_str)

        data = {
            CONF_ACCESS_TOKEN: self._access_token,
            CONF_COUNTRY: self._country,
            CONF_CONNECT_CLIENT_ID: connect_client_id,
            CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_THINQ,
        }
        return self.async_create_entry(title=self._entity_name, data=data)

    ##### common #####
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        return self.async_show_menu(
            step_id="user",
            menu_options=[
                CONF_ENTRY_TYPE_THINQ,
                CONF_ENTRY_TYPE_WEBOSTV,
                CONF_ENTRY_TYPE_SOUNDBAR,
            ],
        )

    ##### thinq (appliance) #####
    async def async_step_thinq(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        """Get the PAT(Personal Access Token) and validate it."""
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            return self.async_show_form(
                step_id="thinq",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCESS_TOKEN): cv.string,
                        vol.Optional(
                            CONF_NAME, default=THINQ_DEFAULT_NAME
                        ): cv.string,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "pat_url": THINQ_PAT_URL,
                },
            )
        self._access_token = user_input.get(CONF_ACCESS_TOKEN)
        self._entity_name = user_input.get(CONF_NAME)

        """ Check if PAT is already configured"""
        unique_id = self._access_token
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_region()

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the seleting the country and language."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="region",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_COUNTRY,
                            default=self._get_default_country_code(),
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=SUPPORTED_COUNTRIES,
                                mode=SelectSelectorMode.DROPDOWN,
                                sort=True,
                            )
                        ),
                    }
                ),
                errors=errors,
            )
        self._country = user_input.get(CONF_COUNTRY)
        return await self._validate_and_create_entry()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        entry_type: str = config_entry.data.get(CONF_ENTRY_TYPE)
        if entry_type in (CONF_ENTRY_TYPE_THINQ, CONF_ENTRY_TYPE_SOUNDBAR):
            return OptionsFlowHandler(config_entry)

        if entry_type == CONF_ENTRY_TYPE_WEBOSTV:
            return WebOsTvOptionsFlowHandler(config_entry)

        raise ConfigEntryError("Invalid entry type: %s.", entry_type)

    ##### Soundbar #####
    async def async_step_soundbar(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search a Soundbar host."""
        if user_input is not None:
            await self._async_soundbar_discover()
            return await self.async_step_soundbar_fill_data()

        return self.async_show_form(step_id="soundbar")

    # search local networks
    async def _async_soundbar_discover(self) -> None:
        """Discover a Soundbar host by port scanning."""
        self._soundbar_host = ""

        hosts: str = "192.168.1.1/24"
        nmap_scanner = PortScanner()
        try:
            results = nmap_scanner.scan(
                hosts=hosts,
                ports=str(SOUNDBAR_PORT),
                arguments="-PS --open -oJ",
            )
            _LOGGER.warning("Port scanning results: %s", results)
        except PortScannerError as e:
            _LOGGER.error("Port scanning failed: %s", e)
            return

        if not results:
            _LOGGER.warning("No scan result.")
            return

        scan_result: dict = results.get("scan")
        if scan_result:
            ip_list = list(scan_result.keys())
            _LOGGER.warning("A list of ip address: %s", ip_list)

            # we need to check real soundbar device here
            # but temporarily set _soundbar_host as the first ip in the list
            self._soundbar_host = ip_list[0]
            _LOGGER.warning("Set soundbar host: %s", self._soundbar_host)

    async def async_step_soundbar_fill_data(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to fill Soundbar data."""
        if user_input is not None:
            return await self._async_soundbar_connect(user_input=user_input)

        return self.async_show_form(
            step_id="soundbar_fill_data",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._soundbar_host
                    ): cv.string,
                    vol.Optional(
                        CONF_NAME, default=SOUNDBAR_DEFAULT_NAME
                    ): cv.string,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        )

    async def _async_soundbar_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Try to connect Soundbar."""
        host: str = user_input.get(CONF_HOST)
        name: str = user_input.get(CONF_NAME)
        _LOGGER.warning("Try to connect. host: %s", host)

        # Try to create a client.
        soundbar_client = await self.hass.async_add_executor_job(
            config_connect, host, SOUNDBAR_PORT
        )
        if soundbar_client is None:
            _LOGGER.warning("Failed to create a Soundbar client.")
            return {"ret": None, "error": "cannot_connect"}

        # Try to get a device info.
        self.hass.async_add_executor_job(soundbar_client.listen)
        device_info = await self.hass.async_add_executor_job(
            config_device, soundbar_client
        )
        if device_info:
            data: dict[str, Any] = {
                CONF_HOST: host,
                CONF_PORT: SOUNDBAR_PORT,
                CONF_NAME: name,
                CONF_SOUNDBAR_MODEL: device_info.get("name"),
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_SOUNDBAR,
            }
            if "uuid" in device_info:
                await self.async_set_unique_id(device_info.get("uuid"))
                self._abort_if_unique_id_configured()
            else:
                self._async_abort_entries_match(data)

            return self.async_create_entry(title=name, data=data)

        return self.async_abort(reason="no_device_info")

    ##### webOS TV #####

    async def _async_search_ssdp_listeners(self) -> None:
        if len(self._ssdp_listeners) > 0:
            for ssdp_listener in self._ssdp_listeners:
                ssdp_listener.async_search()
                if ssdp.is_ipv4_address(ssdp_listener.source):
                    ssdp_listener.async_search(
                        (str(IPV4_BROADCAST), ssdp.SSDP_PORT)
                    )
            try:
                await asyncio.wait_for(self._ssdp_res_fut, timeout=SSDP_MX)
                self._webostv_host = self._ssdp_res_fut.result()
            except TimeoutError:
                _LOGGER.warning("[TimeoutError] Can't find TV on network")

            for ssdp_listener in self._ssdp_listeners:
                ssdp_listener.async_stop()

    async def _async_search_webostv(self) -> None:
        """Start the SSDP Listeners."""

        # Devices are shared between all sources.
        def _on_search(headers: CaseInsensitiveDict) -> None:
            """Search callback."""
            try:
                if (
                    headers.get("ST") == WEBOS_SECOND_SCREEN_ST
                    and self._ssdp_res_fut is not None
                    and not self._ssdp_res_fut.done()
                ):
                    self._ssdp_res_fut.set_result(headers.get("_host"))
            except asyncio.InvalidStateError:
                pass

        _loop = asyncio.get_event_loop()
        self._ssdp_listeners: list[SsdpSearchListener] = []
        self._ssdp_res_fut = _loop.create_future()
        for source_ip in await ssdp.async_build_source_set(self.hass):
            source_ip_str = str(source_ip)
            if source_ip.version == 6:
                source_tuple: AddressTupleVXType = (
                    source_ip_str,
                    0,
                    0,
                    int(getattr(source_ip, "scope_id")),
                )
            else:
                source_tuple = (source_ip_str, 0)
            source, target = ssdp.determine_source_target(source_tuple)
            source = ssdp.fix_ipv6_address_scope_id(source) or source
            self._ssdp_listeners.append(
                SsdpSearchListener(
                    callback=_on_search,
                    loop=_loop,
                    source=source,
                    target=target,
                    timeout=SSDP_MX,
                )
            )
        results = await asyncio.gather(
            *(
                asyncio.Task(listener.async_start(), loop=_loop)
                for listener in self._ssdp_listeners
            ),
            return_exceptions=True,
        )
        failed_listeners = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.debug(
                    "Failed to setup listener for %s: %s",
                    self._ssdp_listeners[idx].source,
                    result,
                )
                failed_listeners.append(self._ssdp_listeners[idx])
        for listener in failed_listeners:
            self._ssdp_listeners.remove(listener)

        await self._async_search_ssdp_listeners()

    async def async_step_webostv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search webOS TV HOST IP using SSDP."""
        self._webostv_host = GUIDE_ENTER_TV_IP
        if user_input is not None:
            await self._async_search_webostv()
            return await self.async_step_webostv_fill_data()
        return self.async_show_form(step_id="webostv")

    async def async_step_webostv_fill_data(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            return await self.async_step_pairing()

        _data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._webostv_host): cv.string,
                vol.Optional(CONF_NAME, default=WEBOS_DEFAULT_NAME): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(
            step_id="webostv_fill_data", data_schema=_data_schema
        )

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display pairing form."""
        self.context[CONF_HOST] = self._host
        errors = {}

        if user_input is not None:
            try:
                client = await async_control_connect(self._host, None)
                self._client_key = client.client_key
            except WebOsTvPairError:
                return self.async_abort(reason="error_pairing")
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    client.hello_info["deviceUUID"],
                    raise_on_progress=False,
                )
                self._abort_if_unique_id_configured({CONF_HOST: self._host})
                return await self.async_step_select_sources()
        return self.async_show_form(step_id="pairing", errors=errors)

    async def async_step_select_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            data = {
                CONF_HOST: self._host,
                CONF_CLIENT_SECRET: self._client_key,
                CONF_SOURCES: user_input[CONF_SOURCES],
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_WEBOSTV,
            }
            return self.async_create_entry(title=self._name, data=data)
        # Get sources
        sources_list = await async_get_sources(self._host, self._client_key)
        if not sources_list:
            errors["base"] = "cannot_retrieve"

        sources_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SOURCES,
                    description={"suggested_value": sources_list},
                ): cv.multi_select(
                    {source: source for source in sources_list}
                ),
            }
        )

        return self.async_show_form(
            step_id="select_sources", data_schema=sources_schema, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        assert discovery_info.ssdp_location
        host = urlparse(discovery_info.ssdp_location).hostname
        assert host
        self._host = host
        self._name = discovery_info.upnp.get(
            ssdp.ATTR_UPNP_FRIENDLY_NAME, WEBOS_DEFAULT_NAME
        )
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._host:
                return self.async_abort(reason="already_in_progress")
        return await self.async_step_pairing()


class OptionsFlowHandler(OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        return self.async_abort(reason="not_supported")


class WebOsTvOptionsFlowHandler(OptionsFlow):
    """Handle options flow for LG webOS TV."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options
        self.host = config_entry.data[CONF_HOST]
        self.key = config_entry.data[CONF_CLIENT_SECRET]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to initialize."""
        return await self.async_step_webostv(user_input)

    async def async_step_webostv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            options_input = {CONF_SOURCES: user_input[CONF_SOURCES]}
            return self.async_create_entry(title="", data=options_input)
        # Get sources
        sources_list = await async_get_sources(self.host, self.key)
        if not sources_list:
            errors["base"] = "cannot_retrieve"

        conf_sources = get_conf_sources(self.config_entry)

        sources = [s for s in conf_sources if s in sources_list]
        if not sources:
            sources = sources_list

        sources_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SOURCES,
                    description={"suggested_value": sources},
                ): cv.multi_select(
                    {source: source for source in sources_list}
                ),
            }
        )

        return self.async_show_form(
            step_id="webostv", data_schema=sources_schema, errors=errors
        )
