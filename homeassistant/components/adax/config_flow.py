"""Config flow for Adax integration."""

import logging
from typing import Any, override

import adax
import adax_local
from adax_local import Adax as AdaxLocal
import aiohttp
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MAC,
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

from .const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    LOCAL_MANUAL,
    WIFI_PSWD,
    WIFI_SSID,
)

_LOGGER = logging.getLogger(__name__)


class AdaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Adax."""

    VERSION = 2

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
                        LOCAL_MANUAL,
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
        if user_input[CONNECTION_TYPE] == LOCAL_MANUAL:
            return await self.async_step_local_manual()
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

    async def async_step_local_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the local manual step."""
        errors: dict[str, str] = {}

        data_schema = probatio.Schema(
            {
                probatio.Required(CONF_IP_ADDRESS): str,
                probatio.Required(CONF_MAC): str,
                probatio.Required(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                    ),
                ),
            }
        )

        if user_input is not None:
            try:
                formatted_mac = format_mac(user_input[CONF_MAC])
                mac_parts = formatted_mac.split(":")
                if len(mac_parts) != 6 or any(len(part) != 2 for part in mac_parts):
                    errors[CONF_MAC] = "invalid_mac"
                clean_mac = "".join(mac_parts)
                unique_id = str(int(clean_mac, 16))
            except ValueError:
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                ip_address = user_input[CONF_IP_ADDRESS].strip()
                token = user_input[CONF_TOKEN].strip()

                client = AdaxLocal(
                    ip_address,
                    token,
                    websession=async_get_clientsession(self.hass, verify_ssl=False),
                )

                try:
                    status = await client.get_status()
                    if not status or status.get("current_temperature") is None:
                        errors["base"] = "cannot_connect"
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error connecting to Adax heater")
                    errors["base"] = "unknown"
                else:
                    if not errors:
                        return self.async_create_entry(
                            title=unique_id,
                            data={
                                CONF_IP_ADDRESS: ip_address,
                                CONF_TOKEN: token,
                                CONF_UNIQUE_ID: unique_id,
                                CONNECTION_TYPE: LOCAL,
                            },
                        )

        return self.async_show_form(
            step_id="local_manual",
            data_schema=self.add_suggested_values_to_schema(
                data_schema, user_input
            ),
            errors=errors,
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
