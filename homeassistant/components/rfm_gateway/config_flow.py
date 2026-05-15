from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import (
    RfmGatewayClient,
    RfmGatewayConnectionError,
    RfmGatewayProtocolError,
)
from .const import (
    CONF_HOST,
    DEFAULT_PORT_HTTP,
    DOMAIN,
)


class RfmGatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _discovered_host: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            host = self._normalize_host(host)

            try:
                capabilities = await self._async_get_capabilities(host)
            except RfmGatewayConnectionError:
                errors["base"] = "cannot_connect"
            except RfmGatewayProtocolError:
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                title = capabilities.device_name or f"RFM Gateway ({host})"
                freq_range = self._format_frequency_range(capabilities.supported_frequency_ranges)
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                    },
                    description=freq_range,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> FlowResult:
        if discovery_info.properties.get("model") != "rfm-gateway":
            return self.async_abort(reason="not_rfm_gateway")

        host = ""

        ip_address = getattr(discovery_info, "ip_address", None)
        if ip_address is not None:
            preferred = self._preferred_discovery_ip(str(ip_address))
            if preferred:
                host = preferred

        if not host:
            for addr in getattr(discovery_info, "ip_addresses", []) or []:
                if addr is None:
                    continue
                preferred = self._preferred_discovery_ip(str(addr))
                if preferred:
                    host = preferred
                    break

        raw_host = self._normalize_host(discovery_info.host or "")
        raw_hostname = self._normalize_host(discovery_info.hostname or "")

        if not host and self._is_ip_address(raw_host):
            host = raw_host

        if not host and self._is_ip_address(raw_hostname):
            host = raw_hostname

        if not host and self._is_usable_discovery_host(raw_host):
            host = raw_host

        if not host and self._is_usable_discovery_host(raw_hostname):
            host = raw_hostname

        if not host:
            return self.async_abort(reason="not_rfm_gateway")

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        pretty_name = f"RFM Gateway {host}"

        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host, "name": pretty_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        host = self._discovered_host
        if host is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            try:
                capabilities = await self._async_get_capabilities(host)
            except RfmGatewayConnectionError:
                errors["base"] = "cannot_connect"
            except RfmGatewayProtocolError:
                errors["base"] = "invalid_response"
            else:
                title = capabilities.device_name or f"RFM Gateway ({host})"
                freq_range = self._format_frequency_range(capabilities.supported_frequency_ranges)
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host},
                    description=freq_range,
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host": host, "port": str(DEFAULT_PORT_HTTP)},
            errors=errors,
        )

    @staticmethod
    def _build_base_url(host: str) -> str:
        if ":" in host and not host.startswith("["):
            return f"http://[{host}]:{DEFAULT_PORT_HTTP}"
        return f"http://{host}:{DEFAULT_PORT_HTTP}"

    async def _async_get_capabilities(self, host: str):
        client = RfmGatewayClient(
            hass=self.hass,
            base_url=self._build_base_url(host),
        )
        return await client.async_get_capabilities()

    async def _async_validate_host(self, host: str) -> None:
        await self._async_get_capabilities(host)

    @staticmethod
    def _format_frequency_range(ranges: list[tuple[int, int]]) -> str:
        if not ranges:
            return ""
        formatted = []
        for min_hz, max_hz in ranges:
            min_mhz = min_hz / 1_000_000
            max_mhz = max_hz / 1_000_000
            formatted.append(f"{min_mhz:.0f}-{max_mhz:.0f} MHz")
        return "Supported: " + ", ".join(formatted)

    @staticmethod
    def _normalize_host(host: str) -> str:
        result = host.strip().rstrip(".")
        if not result:
            return result
        if result.endswith(".local"):
            return result
        if result.startswith("["):
            end = result.find("]")
            if end != -1:
                return result[1:end]
            return result
        try:
            ipaddress.ip_address(result)
            return result
        except ValueError:
            pass
        if result.count(":") == 1:
            return result.rsplit(":", 1)[0]
        return result

    @staticmethod
    def _is_ip_address(value: str) -> bool:
        if not value:
            return False
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _preferred_discovery_ip(value: str) -> str | None:
        if not value:
            return None

        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return None

        if ip.version == 4:
            return str(ip)

        if ip.is_link_local:
            return None

        return str(ip)

    @staticmethod
    def _is_usable_discovery_host(value: str) -> bool:
        if not value:
            return False
        if "_http._tcp" in value:
            return False
        if "._" in value:
            return False
        if "_" in value:
            return False
        return True