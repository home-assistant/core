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

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_INVERT_POSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)

API_VERSION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(value="1", label="API 1"),
            SelectOptionDict(value="2", label="API 2"),
        ],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_API_VERSION,
    )
)


class SlideConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for slide_local."""

    _mac: str = ""
    _host: str = ""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_test_connection(
        self, user_input: dict[str, str | int]
    ) -> dict[str, str]:
        """Reusable Auth Helper."""
        slide = SlideLocalApi()
        await slide.slide_add(
            user_input[CONF_HOST],
            user_input.get(CONF_PASSWORD, ""),
            user_input[CONF_API_VERSION],
        )

        try:
            result = await slide.slide_info(user_input[CONF_HOST])
        except (ClientConnectionError, ClientTimeoutError):
            return {"base": "cannot_connect"}
        except (AuthenticationFailed, DigestAuthCalcError):
            return {"base": "invalid_auth"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Exception occurred during connection test")
            return {"base": "unknown"}

        self._mac = result["mac"]

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            user_input[CONF_API_VERSION] = int(user_input[CONF_API_VERSION])

            if not (errors := await self.async_test_connection(user_input)):
                await self.async_set_unique_id(self._mac)
                user_input |= {CONF_MAC: format_mac(self._mac)}

                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                    options={CONF_INVERT_POSITION: False},
                )

        if user_input is not None and user_input.get(CONF_HOST) is not None:
            self._host = user_input[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_API_VERSION, default="2"): API_VERSION_SELECTOR,
                    vol.Required(
                        CONF_INVERT_POSITION, default=False
                    ): BooleanSelector(),
                }
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

        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.host})

        self._host = discovery_info.host

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

            if not await self.async_test_connection(user_input):
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                    options={CONF_INVERT_POSITION: False},
                )
            return self.async_abort(reason="discovery_connection_failed")

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "host": self._host,
            },
        )
