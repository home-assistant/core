"""Config flow for slide_local integration."""

from __future__ import annotations

import logging
from typing import Any

from goslideapi.goslideapi import (
    AuthenticationFailed,
    ClientConnectionError,
    ClientTimeoutError,
    DigestAuthCalcError,
    GoSlideLocal as SlideLocalApi,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_INVERT_POSITION, DOMAIN
from .coordinator import SlideConfigEntry

_LOGGER = logging.getLogger(__name__)


class SlideConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for slide_local."""

    _mac: str = ""
    _host: str = ""
    _api_version: int | None = None

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SlideConfigEntry,
    ) -> SlideOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SlideOptionsFlowHandler()

    async def async_test_connection(
        self, user_input: dict[str, str | int]
    ) -> dict[str, str]:
        """Reusable Auth Helper."""
        slide = SlideLocalApi()

        # first test, if API version 2 is working
        await slide.slide_add(
            user_input[CONF_HOST],
            user_input.get(CONF_PASSWORD, ""),
            2,
        )

        try:
            result = await slide.slide_info(user_input[CONF_HOST])
        except (ClientConnectionError, ClientTimeoutError):
            return {"base": "cannot_connect"}
        except (AuthenticationFailed, DigestAuthCalcError):
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Exception occurred during connection test")
            return {"base": "unknown"}

        if result is not None:
            self._api_version = 2
            self._mac = format_mac(result["mac"])
            return {}

        # API version 2 is not working, try API version 1 instead
        await slide.slide_add(
            user_input[CONF_HOST],
            user_input.get(CONF_PASSWORD, ""),
            1,
        )

        try:
            result = await slide.slide_info(user_input[CONF_HOST])
        except (ClientConnectionError, ClientTimeoutError):
            return {"base": "cannot_connect"}
        except (AuthenticationFailed, DigestAuthCalcError):
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Exception occurred during connection test")
            return {"base": "unknown"}

        if result is None:
            # API version 1 isn't working either
            return {"base": "unknown"}

        self._api_version = 1
        self._mac = format_mac(result["mac"])

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := await self.async_test_connection(user_input)):
                await self.async_set_unique_id(self._mac)
                self._abort_if_unique_id_configured()
                user_input |= {
                    CONF_MAC: self._mac,
                    CONF_API_VERSION: self._api_version,
                }

                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                    options={CONF_INVERT_POSITION: False},
                )

        if user_input is not None and user_input.get(CONF_HOST) is not None:
            self._host = user_input[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Optional(CONF_PASSWORD): str,
                    }
                ),
                {CONF_HOST: self._host},
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self.async_test_connection(user_input)):
                await self.async_set_unique_id(self._mac)
                self._abort_if_unique_id_mismatch(
                    description_placeholders={CONF_MAC: self._mac}
                )
                user_input |= {
                    CONF_API_VERSION: self._api_version,
                }

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        entry: SlideConfigEntry = self._get_reconfigure_entry()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
                {
                    CONF_HOST: entry.data[CONF_HOST],
                    CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
                },
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # id is in the format 'slide_000000000000'
        self._mac = format_mac(str(discovery_info.properties.get("id"))[6:])

        await self.async_set_unique_id(self._mac)

        ip = str(discovery_info.ip_address)
        _LOGGER.debug("Slide device discovered, ip %s", ip)

        self._abort_if_unique_id_configured({CONF_HOST: ip}, reload_on_update=True)

        errors = {}
        if errors := await self.async_test_connection(
            {
                CONF_HOST: ip,
            }
        ):
            return self.async_abort(
                reason="discovery_connection_failed",
                description_placeholders={
                    "error": errors["base"],
                },
            )

        self._host = ip

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""

        if user_input is not None:
            user_input |= {
                CONF_HOST: self._host,
                CONF_API_VERSION: 2,
                CONF_MAC: format_mac(self._mac),
            }
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input,
                options={CONF_INVERT_POSITION: False},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "host": self._host,
            },
        )


class SlideOptionsFlowHandler(OptionsFlow):
    """Handle a options flow for slide_local."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_INVERT_POSITION): bool,
                    }
                ),
                {CONF_INVERT_POSITION: self.config_entry.options[CONF_INVERT_POSITION]},
            ),
        )
