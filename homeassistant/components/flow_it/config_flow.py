"""Config flow for Flow-it integration."""

import logging
from typing import Any, override

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    vmc = FlowItVMCMachine(
        data[CONF_HOST],
        data[CONF_PASSWORD],
        data[CONF_USERNAME],
        session=get_async_client(hass),
    )
    info = await vmc.get_info()
    await vmc.refresh_state()
    assert vmc.state is not None
    return {
        "title": info.hostname,
        "unique_id": vmc.state.name,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flow-it."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]

            # Ensure host has protocol
            if not URL(host).scheme:
                host = str(URL.build(scheme="http", host=host))
                user_input[CONF_HOST] = host

            try:
                info = await validate_input(self.hass, user_input)
            except FlowItAuthError:
                errors["base"] = "invalid_auth"
            except FlowItConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=info["title"], data=user_input)

        # Pre-fill data from discovery if available
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=self._discovery_info.get(CONF_HOST, "")
                ): str,
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, autocomplete="username"
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD, autocomplete="current-password"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = self._discovery_info[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            # Ensure host has protocol
            if not URL(host).scheme:
                host = str(URL.build(scheme="http", host=host))

            data = {
                CONF_HOST: host,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            }

            try:
                info = await validate_input(self.hass, data)
            except FlowItAuthError:
                errors["base"] = "invalid_auth"
            except FlowItConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured(updates=data)
                return self.async_create_entry(title=info["title"], data=data)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, autocomplete="username"
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD, autocomplete="current-password"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "name": self._discovery_info.get(
                    "friendly_name",
                    self._discovery_info[CONF_HOST].removesuffix(".local"),
                )
            },
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        hostname = discovery_info.hostname.rstrip(".").removesuffix(".local")
        friendly_name = discovery_info.name.removesuffix("._tbk_vmc._tcp.local.")

        self._discovery_info = {
            CONF_HOST: hostname,
            "friendly_name": friendly_name,
        }

        # Check if already configured
        self._async_abort_entries_match({CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: hostname})
        self._async_abort_entries_match({CONF_HOST: f"http://{host}"})
        self._async_abort_entries_match({CONF_HOST: f"http://{hostname}"})

        self.context.update({"title_placeholders": {"name": friendly_name}})

        return await self.async_step_zeroconf_confirm()
