"""Config flow for Adax integration."""

import asyncio
import logging
import ssl
from typing import Any, override

import adax
import adax_local
from adax_local import Adax as AdaxLocal
import aiohttp
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    WIFI_PSWD,
    WIFI_SSID,
)

_LOGGER = logging.getLogger(__name__)


async def is_adax_tls_device(ip: str, timeout: float = 2.0) -> bool:
    """Probe port 443 to fingerprint the device via TLS certificate subject.

    This is a discovery heuristic to filter out non-Adax devices sharing
    generic hostnames, not an authentication boundary. Adax heaters use
    self-signed certificates on the local network.
    """
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443, ssl=ssl_ctx),
            timeout=timeout,
        )
        ssl_obj = writer.get_extra_info("ssl_object")
        der_cert = ssl_obj.getpeercert(binary_form=True) if ssl_obj else None
        writer.close()
        await writer.wait_closed()

        if not der_cert:
            return False

        cert = x509.load_der_x509_certificate(der_cert, default_backend())
        common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if common_names and common_names[0].value == "ADAX DEVICE":
            return True

    except (TimeoutError, OSError, ssl.SSLError, ValueError) as err:
        _LOGGER.debug("TLS check failed for %s: %s", ip, err)
        return False

    return False


class AdaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Adax."""

    VERSION = 2

    _discovered_ip: str | None = None
    _discovered_mac: str | None = None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        formatted_mac = format_mac(discovery_info.macaddress)
        clean_mac = "".join(formatted_mac.split(":"))
        unique_id = str(int(clean_mac, 16))

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.ip}
        )

        if not await is_adax_tls_device(discovery_info.ip):
            _LOGGER.debug(
                "Device at %s matched DHCP rule but is not an ADAX DEVICE. Aborting",
                discovery_info.ip,
            )
            return self.async_abort(reason="not_adax_device")

        self._discovered_ip = discovery_info.ip
        self._discovered_mac = formatted_mac

        self.context["title_placeholders"] = {"ip_address": discovery_info.ip}

        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and ask for the local token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            _LOGGER.info(
                "Attempting connection to discovered Adax heater at IP %s (MAC: %s)",
                self._discovered_ip,
                self._discovered_mac,
            )
            client = AdaxLocal(
                self._discovered_ip,
                token,
                websession=async_get_clientsession(self.hass, verify_ssl=False),
            )
            try:
                status = await client.get_status()
                if not status or status.get("current_temperature") is None:
                    errors["base"] = "cannot_connect"
            except aiohttp.ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to Adax heater")
                errors["base"] = "unknown"
            else:
                if not errors:
                    assert self.unique_id is not None
                    return self.async_create_entry(
                        title=self.unique_id,
                        data={
                            CONF_IP_ADDRESS: self._discovered_ip,
                            CONF_TOKEN: token,
                            CONF_UNIQUE_ID: self.unique_id,
                            CONNECTION_TYPE: LOCAL,
                        },
                    )

        return self.async_show_form(
            step_id="dhcp_confirm",
            description_placeholders={
                "ip_address": self._discovered_ip or "",
                "mac": self._discovered_mac or "",
            },
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = probatio.Schema(
            {
                probatio.Required(CONNECTION_TYPE, default=CLOUD): probatio.In(
                    (
                        CLOUD,
                        LOCAL,
                    )
                )
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        if user_input[CONNECTION_TYPE] == LOCAL:
            return await self.async_step_local()
        return await self.async_step_cloud()

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the local step."""
        data_schema = probatio.Schema(
            {
                probatio.Required(WIFI_SSID): str,
                probatio.Required(WIFI_PSWD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    ),
                ),
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
            )

        wifi_ssid = user_input[WIFI_SSID]
        wifi_pswd = user_input[WIFI_PSWD].replace(" ", "")
        configurator = adax_local.AdaxConfig(wifi_ssid, wifi_pswd)

        try:
            device_configured = await configurator.configure_device()
        except adax_local.HeaterNotAvailable:
            return self.async_abort(reason="heater_not_available")
        except adax_local.HeaterNotFound:
            return self.async_abort(reason="heater_not_found")
        except adax_local.InvalidWifiCred:
            return self.async_abort(reason="invalid_auth")

        if not device_configured:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        unique_id = str(configurator.mac_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_IP_ADDRESS: configurator.device_ip,
                CONF_TOKEN: configurator.access_token,
                CONF_UNIQUE_ID: unique_id,
                CONNECTION_TYPE: LOCAL,
            },
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud step."""
        data_schema = probatio.Schema(
            {
                probatio.Required(ACCOUNT_ID): int,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="cloud", data_schema=data_schema)

        errors = {}

        await self.async_set_unique_id(str(user_input[ACCOUNT_ID]))
        self._abort_if_unique_id_configured()

        account_id = user_input[ACCOUNT_ID]
        password = user_input[CONF_PASSWORD].replace(" ", "")

        token = await adax.get_adax_token(
            async_get_clientsession(self.hass), account_id, password
        )
        if token is None:
            _LOGGER.debug("Adax: Failed to login to retrieve token")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors=errors,
            )

        return self.async_create_entry(
            title=str(user_input[ACCOUNT_ID]),
            data={
                ACCOUNT_ID: account_id,
                CONF_PASSWORD: password,
                CONNECTION_TYPE: CLOUD,
            },
        )
