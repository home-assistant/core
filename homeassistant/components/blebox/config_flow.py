"""Config flow for BleBox devices integration."""

import asyncio
import logging
from typing import Any, TypedDict, cast

from blebox_uniapi.box import Box
from blebox_uniapi.error import (
    Error,
    UnauthorizedRequest,
    UnsupportedBoxResponse,
    UnsupportedBoxVersion,
)
from blebox_uniapi.session import ApiHost
import voluptuous as vol
from zeroconf import BadTypeInNameException, DNSPointer, IPVersion
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo
from zeroconf.const import _CLASS_IN, _TYPE_PTR

from homeassistant.components import zeroconf as zeroconf_component
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import get_maybe_authenticated_session
from .const import (
    ADDRESS_ALREADY_CONFIGURED,
    CANNOT_CONNECT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SETUP_TIMEOUT,
    DOMAIN,
    UNKNOWN,
    UNSUPPORTED_VERSION,
    ZEROCONF_TYPE,
)

_LOGGER = logging.getLogger(__name__)

MDNS_SCAN_TIMEOUT = 1


def create_schema(previous_input=None):
    """Create a schema with given values as default."""
    if previous_input is not None:
        host = previous_input[CONF_HOST]
        port = previous_input[CONF_PORT]
    else:
        host = DEFAULT_HOST
        port = DEFAULT_PORT

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
            vol.Inclusive(CONF_USERNAME, "auth"): str,
            vol.Inclusive(CONF_PASSWORD, "auth"): str,
        }
    )


LOG_MSG = {
    UNSUPPORTED_VERSION: "Outdated firmware",
    CANNOT_CONNECT: "Failed to identify device",
    UNKNOWN: "Unknown error while identifying device",
}


class DiscoveredDevice(TypedDict):
    """A device discovered during an active mDNS scan."""

    host: str
    port: int
    name: str
    unique_id: str


async def async_scan_mdns(hass: HomeAssistant) -> list[tuple[str, int]]:
    """Actively scan for BleBox devices via mDNS and return (host, port) pairs."""
    aiozc = zeroconf_component.async_get_async_zeroconf(hass)

    browser = AsyncServiceBrowser(
        aiozc.zeroconf,
        [ZEROCONF_TYPE],
        handlers=[lambda zeroconf, service_type, name, state_change: None],
    )
    try:
        await asyncio.sleep(MDNS_SCAN_TIMEOUT)
    finally:
        await browser.async_cancel()

    all_infos: list[AsyncServiceInfo] = []
    to_request: list[AsyncServiceInfo] = []
    for record in cast(
        list[DNSPointer],
        list(
            aiozc.zeroconf.cache.async_all_by_details(
                ZEROCONF_TYPE, _TYPE_PTR, _CLASS_IN
            )
        ),
    ):
        try:
            info = AsyncServiceInfo(ZEROCONF_TYPE, record.alias)
        except BadTypeInNameException:
            continue
        if not info.load_from_cache(aiozc.zeroconf):
            to_request.append(info)
        all_infos.append(info)

    if to_request:
        await asyncio.gather(
            *(info.async_request(aiozc.zeroconf, 3000) for info in to_request)
        )

    found: list[tuple[str, int]] = []
    for info in all_infos:
        port = info.port or DEFAULT_PORT
        found.extend((addr, port) for addr in info.parsed_addresses(IPVersion.V4Only))

    return found


class BleBoxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BleBox devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the BleBox config flow."""
        self.device_config: dict[str, Any] = {}
        self._discovered_devices: dict[str, DiscoveredDevice] = {}

    def handle_step_exception(
        self, step, exception, schema, host, port, message_id, log_fn
    ):
        """Handle step exceptions."""
        log_fn("%s at %s:%d (%s)", LOG_MSG[message_id], host, port, exception)

        return self.async_show_form(
            step_id=step,
            data_schema=schema,
            errors={"base": message_id},
            description_placeholders={"address": f"{host}:{port}"},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        hass = self.hass
        ipaddress = (discovery_info.host, discovery_info.port)
        self.device_config["host"] = discovery_info.host
        self.device_config["port"] = discovery_info.port

        websession = async_get_clientsession(hass)

        api_host = ApiHost(
            *ipaddress, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER
        )

        try:
            product = await Box.async_from_host(api_host)
        except UnsupportedBoxVersion:
            return self.async_abort(reason="unsupported_device_version")
        except UnsupportedBoxResponse:
            return self.async_abort(reason="unsupported_device_response")

        self.device_config["name"] = product.name
        # Check if configured but IP changed since
        await self.async_set_unique_id(product.unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
        self.context.update(
            {
                "title_placeholders": {
                    "name": self.device_config["name"],
                    "host": self.device_config["host"],
                },
                "configuration_url": f"http://{discovery_info.host}",
            }
        )
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.device_config["name"],
                data={
                    "host": self.device_config["host"],
                    "port": self.device_config["port"],
                },
            )

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "name": self.device_config["name"],
                "host": self.device_config["host"],
                "port": self.device_config["port"],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial user-triggered config step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["scan", "manual"],
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan network via mDNS, then show device picker."""
        hass = self.hass
        current_hosts = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        found_addresses = await async_scan_mdns(hass)
        candidates = [
            (host, port) for host, port in found_addresses if host not in current_hosts
        ]

        websession = async_get_clientsession(hass)

        async def _probe(host: str, port: int) -> DiscoveredDevice | None:
            api_host = ApiHost(
                host, port, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER
            )
            try:
                product = await Box.async_from_host(api_host)
            except (
                Error,
                UnsupportedBoxVersion,
                UnsupportedBoxResponse,
                UnauthorizedRequest,
                TimeoutError,
            ) as ex:
                _LOGGER.debug("Probe failed for %s:%d (%s)", host, port, ex)
                return None
            return DiscoveredDevice(
                host=host, port=port, name=product.name, unique_id=product.unique_id
            )

        results = await asyncio.gather(*(_probe(h, p) for h, p in candidates))

        self._discovered_devices = {
            f"{device['host']}:{device['port']}": device
            for device in results
            if device is not None
        }

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return await self.async_step_pick_device()

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a discovered device."""
        if user_input is not None:
            device = self._discovered_devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(device["unique_id"], raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=device["name"],
                data={CONF_HOST: device["host"], CONF_PORT: device["port"]},
            )

        options = [
            SelectOptionDict(value=key, label=f"{dev['name']} ({dev['host']})")
            for key, dev in self._discovered_devices.items()
        ]

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        schema = create_schema(user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=schema,
            )

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        for entry in self._async_current_entries():
            if host == entry.data[CONF_HOST] and port == entry.data[CONF_PORT]:
                return self.async_abort(
                    reason=ADDRESS_ALREADY_CONFIGURED,
                    description_placeholders={"address": f"{host}:{port}"},
                )

        try:
            return await self._async_create_entry_from_host(
                host, port, username, password
            )
        except UnsupportedBoxVersion as ex:
            return self.handle_step_exception(
                "manual", ex, schema, host, port, UNSUPPORTED_VERSION, _LOGGER.debug
            )
        except UnauthorizedRequest as ex:
            return self.handle_step_exception(
                "manual", ex, schema, host, port, CANNOT_CONNECT, _LOGGER.error
            )
        except Error as ex:
            return self.handle_step_exception(
                "manual", ex, schema, host, port, CANNOT_CONNECT, _LOGGER.warning
            )
        except RuntimeError as ex:
            return self.handle_step_exception(
                "manual", ex, schema, host, port, UNKNOWN, _LOGGER.error
            )

    async def _async_create_entry_from_host(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
    ) -> ConfigFlowResult:
        """Connect to device, set unique ID and create config entry."""
        hass = self.hass
        websession = get_maybe_authenticated_session(hass, password, username)
        api_host = ApiHost(
            host, port, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER
        )
        product = await Box.async_from_host(api_host)

        await self.async_set_unique_id(product.unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        data: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
        if username:
            data[CONF_USERNAME] = username
        if password:
            data[CONF_PASSWORD] = password
        return self.async_create_entry(title=product.name, data=data)
