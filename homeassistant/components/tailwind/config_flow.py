"""Config flow to configure the Tailwind integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from gotailwind import (
    MIN_REQUIRED_FIRMWARE_VERSION,
    Tailwind,
    TailwindAuthenticationError,
    TailwindConnectionError,
    TailwindUnsupportedFirmwareVersionError,
    tailwind_device_id_to_mac_address,
)
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER

LOCAL_CONTROL_KEY_URL = (
    "https://web.gotailwind.com/client/integration/local-control-key"
)


class TailwindFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Tailwind config flow."""

    VERSION = 1

    host: str
    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                return await self._async_step_create_entry(
                    host=user_input[CONF_HOST],
                    token=user_input[CONF_TOKEN],
                )
            except AbortFlow:
                raise
            except TailwindAuthenticationError:
                errors[CONF_TOKEN] = "invalid_auth"
            except TailwindConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                    vol.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"url": LOCAL_CONTROL_KEY_URL},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of a Tailwind device."""
        if not (device_id := discovery_info.properties.get("device_id")):
            return self.async_abort(reason="no_device_id")

        if (
            version := discovery_info.properties.get("SW ver")
        ) and version < MIN_REQUIRED_FIRMWARE_VERSION:
            return self.async_abort(reason="unsupported_firmware")

        await self.async_set_unique_id(
            format_mac(tailwind_device_id_to_mac_address(device_id))
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.host = discovery_info.host
        self.context.update(
            {
                "title_placeholders": {
                    "name": f"Tailwind {discovery_info.properties.get('product')}"
                },
                "configuration_url": LOCAL_CONTROL_KEY_URL,
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        errors = {}

        if user_input is not None:
            try:
                return await self._async_step_create_entry(
                    host=self.host,
                    token=user_input[CONF_TOKEN],
                )
            except TailwindAuthenticationError:
                errors[CONF_TOKEN] = "invalid_auth"
            except TailwindConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"url": LOCAL_CONTROL_KEY_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with a Tailwind device."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a Tailwind device."""
        errors = {}

        if user_input is not None and self.reauth_entry:
            try:
                return await self._async_step_create_entry(
                    host=self.reauth_entry.data[CONF_HOST],
                    token=user_input[CONF_TOKEN],
                )
            except TailwindAuthenticationError:
                errors[CONF_TOKEN] = "invalid_auth"
            except TailwindConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"url": LOCAL_CONTROL_KEY_URL},
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery to update existing entries.

        This flow is triggered only by DHCP discovery of known devices.
        """
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        # This situation should never happen, as Home Assistant will only
        # send updates for existing entries. In case it does, we'll just
        # abort the flow with an unknown error.
        return self.async_abort(reason="unknown")

    async def _async_step_create_entry(
        self, *, host: str, token: str
    ) -> ConfigFlowResult:
        """Create entry."""
        tailwind = Tailwind(
            host=host, token=token, session=async_get_clientsession(self.hass)
        )

        try:
            status = await tailwind.status()
        except TailwindUnsupportedFirmwareVersionError:
            return self.async_abort(reason="unsupported_firmware")

        if self.reauth_entry:
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                data={
                    CONF_HOST: host,
                    CONF_TOKEN: token,
                },
            )

        await self.async_set_unique_id(
            format_mac(status.mac_address), raise_on_progress=False
        )
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: host,
                CONF_TOKEN: token,
            }
        )

        return self.async_create_entry(
            title=f"Tailwind {status.product}",
            data={CONF_HOST: host, CONF_TOKEN: token},
        )
