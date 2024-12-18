"""Config flow to configure the Peblar integration."""

from __future__ import annotations

from typing import Any

from aiohttp import CookieJar
from peblar import Peblar, PeblarAuthenticationError, PeblarConnectionError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class PeblarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Peblar config flow."""

    VERSION = 1

    _host: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            peblar = Peblar(
                host=user_input[CONF_HOST],
                session=async_create_clientsession(
                    self.hass, cookie_jar=CookieJar(unsafe=True)
                ),
            )
            try:
                await peblar.login(password=user_input[CONF_PASSWORD])
                info = await peblar.system_information()
            except PeblarAuthenticationError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except PeblarConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    info.product_serial_number, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Peblar", data=user_input)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of a Peblar device."""
        if not (sn := discovery_info.properties.get("sn")):
            return self.async_abort(reason="no_serial_number")

        await self.async_set_unique_id(sn)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self._host = discovery_info.host
        self.context.update({"configuration_url": f"http://{discovery_info.host}"})
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        errors = {}

        if user_input is not None:
            peblar = Peblar(
                host=self._host,
                session=async_create_clientsession(
                    self.hass, cookie_jar=CookieJar(unsafe=True)
                ),
            )
            try:
                await peblar.login(password=user_input[CONF_PASSWORD])
            except PeblarAuthenticationError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Peblar",
                    data={
                        CONF_HOST: self._host,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )
