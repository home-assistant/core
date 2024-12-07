"""Config flow for Yamaha."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from requests.exceptions import ConnectionError
import rxv
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import get_upnp_desc
from .const import (
    CONF_SERIAL,
    CONF_UPNP_DESC,
    DEFAULT_NAME,
    DOMAIN,
    OPTION_INPUT_SOURCES,
    OPTION_INPUT_SOURCES_IGNORE,
)
from .yamaha_config_info import YamahaConfigInfo

_LOGGER = logging.getLogger(__name__)


class YamahaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Yamaha config flow."""

    VERSION = 1

    serial_number: str | None = None
    host: str
    upnp_description: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form()

        host = user_input[CONF_HOST]

        # Check if device is a Yamaha receiver
        try:
            upnp_desc: str = await get_upnp_desc(self.hass, host)
            info = await YamahaConfigInfo.get_rxv_details(upnp_desc, self.hass)
        except ConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            if info is None:
                return self.async_abort(reason="cannot_connect")
            if (serial_number := info.serial_number) is None:
                await self._async_handle_discovery_without_unique_id()
            else:
                await self.async_set_unique_id(serial_number, raise_on_progress=False)
                self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={
                CONF_HOST: host,
                CONF_SERIAL: serial_number,
                CONF_UPNP_DESC: await get_upnp_desc(self.hass, host),
            },
            options={
                OPTION_INPUT_SOURCES_IGNORE: user_input.get(OPTION_INPUT_SOURCES_IGNORE)
                or [],
                OPTION_INPUT_SOURCES: user_input.get(OPTION_INPUT_SOURCES) or {},
            },
        )

    def _show_setup_form(self, errors: dict | None = None) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle ssdp discoveries."""
        assert discovery_info.ssdp_location is not None
        if not await YamahaConfigInfo.check_yamaha_ssdp(
            discovery_info.ssdp_location, self.hass
        ):
            return self.async_abort(reason="yxc_control_url_missing")
        self.serial_number = discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]
        self.upnp_description = discovery_info.ssdp_location

        # ssdp_location and hostname have been checked in check_yamaha_ssdp so it is safe to ignore type assignment
        self.host = urlparse(discovery_info.ssdp_location).hostname  # type: ignore[assignment]

        await self.async_set_unique_id(self.serial_number)
        self._abort_if_unique_id_configured(
            {
                CONF_HOST: self.host,
                CONF_UPNP_DESC: self.upnp_description,
            }
        )
        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.upnp.get(
                        ssdp.ATTR_UPNP_FRIENDLY_NAME, self.host
                    )
                }
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_HOST: self.host,
                    CONF_SERIAL: self.serial_number,
                    CONF_UPNP_DESC: self.upnp_description,
                },
                options={
                    OPTION_INPUT_SOURCES_IGNORE: user_input.get(
                        OPTION_INPUT_SOURCES_IGNORE
                    )
                    or [],
                    OPTION_INPUT_SOURCES: user_input.get(OPTION_INPUT_SOURCES) or {},
                },
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_import(self, import_data: dict) -> ConfigFlowResult:
        """Import data from configuration.yaml into the config flow."""
        return await self.async_step_user(import_data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return YamahaOptionsFlowHandler(config_entry)


class YamahaOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Yamaha."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._input_sources_ignore: list[str] = config_entry.options[
            OPTION_INPUT_SOURCES_IGNORE
        ]
        self._input_sources: dict[str, str] = config_entry.options[OPTION_INPUT_SOURCES]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        yamaha: rxv.RXV = self.config_entry.runtime_data
        inputs: dict[str, str] = await self.hass.async_add_executor_job(yamaha.inputs)

        if user_input is not None:
            sources_store: dict[str, str] = {
                k: v for k, v in user_input.items() if k in inputs and v != ""
            }

            return self.async_create_entry(
                data={
                    OPTION_INPUT_SOURCES: sources_store,
                    OPTION_INPUT_SOURCES_IGNORE: user_input.get(
                        OPTION_INPUT_SOURCES_IGNORE
                    ),
                }
            )

        schema_dict: dict[Any, Selector] = {}
        available_inputs = [
            SelectOptionDict(value=k, label=k) for k, v in inputs.items()
        ]

        schema_dict[vol.Optional(OPTION_INPUT_SOURCES_IGNORE)] = SelectSelector(
            SelectSelectorConfig(
                options=available_inputs,
                mode=SelectSelectorMode.DROPDOWN,
                multiple=True,
            )
        )

        for source in inputs:
            if source not in self._input_sources_ignore:
                schema_dict[vol.Optional(source, default="")] = TextSelector()

        options = self.config_entry.options.copy()
        if OPTION_INPUT_SOURCES_IGNORE in self.config_entry.options:
            options[OPTION_INPUT_SOURCES_IGNORE] = self.config_entry.options[
                OPTION_INPUT_SOURCES_IGNORE
            ]
        if OPTION_INPUT_SOURCES in self.config_entry.options:
            for source, source_name in self.config_entry.options[
                OPTION_INPUT_SOURCES
            ].items():
                options[source] = source_name

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema_dict), options
            ),
        )
