"""Config flow for Mitsubishi Comfort integration."""

from __future__ import annotations

import logging
from typing import Any

from mitsubishi_comfort import MitsubishiCloudAccount
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_CONNECT_TIMEOUT, CONF_RESPONSE_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MitsubishiComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mitsubishi Comfort."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            account = MitsubishiCloudAccount(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            try:
                if not await account.login():
                    errors["base"] = "invalid_auth"
                else:
                    devices = await account.discover_devices()
                    if not devices:
                        errors["base"] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title=user_input[CONF_USERNAME],
                            data={
                                CONF_USERNAME: user_input[CONF_USERNAME],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                            },
                        )
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            finally:
                await account.close()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery -- store IP for later use."""
        _LOGGER.info(
            "DHCP discovered: %s (%s)", discovery_info.ip, discovery_info.macaddress
        )
        discovered = self.hass.data.setdefault(f"{DOMAIN}_dhcp_discovered", {})
        discovered[discovery_info.macaddress] = discovery_info.ip
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MitsubishiComfortOptionsFlow:
        """Return the options flow handler."""
        return MitsubishiComfortOptionsFlow()


class MitsubishiComfortOptionsFlow(OptionsFlow):
    """Handle options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECT_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_CONNECT_TIMEOUT, 1.2
                        ),
                    ): vol.Coerce(float),
                    vol.Required(
                        CONF_RESPONSE_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_RESPONSE_TIMEOUT, 8.0
                        ),
                    ): vol.Coerce(float),
                }
            ),
        )
