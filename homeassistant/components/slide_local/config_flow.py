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

from homeassistant.components.dhcp import DhcpServiceInfo
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

from . import SlideConfigEntry
from .const import CONF_INVERT_POSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)

BOOLEAN_SELECTOR = BooleanSelector()

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

    _entry: SlideConfigEntry | None = None
    _mac: str = ""
    _ip: str = ""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_test_connection(
        self, user_input: dict[str, str | int]
    ) -> dict[str, str]:
        """Reusable Auth Helper."""
        slide = SlideLocalApi()
        await slide.slide_add(
            user_input[CONF_HOST],
            user_input[CONF_PASSWORD],
            user_input[CONF_API_VERSION],
        )

        try:
            result = await slide.slide_info(user_input[CONF_HOST])
            self._mac = result.get("mac", "")
        except (ClientConnectionError, ClientTimeoutError):
            return {"base": "cannot_connect"}
        except (AuthenticationFailed, DigestAuthCalcError):
            return {"base": "invalid_auth"}
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(e)
            return {"base": "unknown"}

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors = {}
        if user_input is not None and user_input.get(CONF_API_VERSION) is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            user_input[CONF_API_VERSION] = int(user_input[CONF_API_VERSION])

            if not (errors := await self.async_test_connection(user_input)):
                user_input |= {CONF_MAC: format_mac(self._mac)}

                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        if user_input is not None and user_input.get(CONF_HOST) is not None:
            self._ip = user_input[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._ip): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_API_VERSION, default="2"): API_VERSION_SELECTOR,
                    vol.Required(CONF_INVERT_POSITION, default=False): BOOLEAN_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.ip})
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})

        self._mac = format_mac(discovery_info.macaddress)
        self._ip = discovery_info.ip

        return await self.async_step_user()
