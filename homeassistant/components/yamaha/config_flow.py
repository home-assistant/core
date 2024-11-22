"""Config flow for Yamaha."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from requests.exceptions import ConnectionError
import rxv
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import get_upnp_serial_and_model
from .const import (
    CONF_MODEL,
    CONF_SERIAL,
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
    model: str | None = None
    host: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form()

        host = user_input[CONF_HOST]
        serial_number = None
        model = None

        errors = {}
        # Check if device is a Yamaha receiver
        try:
            info = YamahaConfigInfo(host)
            await self.hass.async_add_executor_job(rxv.RXV, info.ctrl_url)
            serial_number, model = await get_upnp_serial_and_model(self.hass, host)
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if serial_number is None:
                errors["base"] = "no_yamaha_device"

        if not errors:
            await self.async_set_unique_id(serial_number, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=model or DEFAULT_NAME,
                data={
                    CONF_HOST: host,
                    CONF_MODEL: model,
                    CONF_SERIAL: serial_number,
                    CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                },
                options={
                    OPTION_INPUT_SOURCES_IGNORE: user_input.get(
                        OPTION_INPUT_SOURCES_IGNORE
                    )
                    or [],
                    OPTION_INPUT_SOURCES: user_input.get(OPTION_INPUT_SOURCES) or {},
                },
            )

        return self._show_setup_form(errors)

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
            discovery_info.ssdp_location, async_get_clientsession(self.hass)
        ):
            return self.async_abort(reason="yxc_control_url_missing")
        self.serial_number = discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]
        self.model = discovery_info.upnp[ssdp.ATTR_UPNP_MODEL_NAME]

        # ssdp_location and hostname have been checked in check_yamaha_ssdp so it is safe to ignore type assignment
        self.host = urlparse(discovery_info.ssdp_location).hostname  # type: ignore[assignment]

        await self.async_set_unique_id(self.serial_number)
        self._abort_if_unique_id_configured(
            {
                CONF_HOST: self.host,
                CONF_NAME: self.model,
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

    async def async_step_confirm(
        self, user_input=None
    ) -> data_entry_flow.ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.model or DEFAULT_NAME,
                data={
                    CONF_HOST: self.host,
                    CONF_MODEL: self.model,
                    CONF_SERIAL: self.serial_number,
                    CONF_NAME: DEFAULT_NAME,
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
        res = await self.async_step_user(import_data)
        if res["type"] == FlowResultType.CREATE_ENTRY:
            _LOGGER.info(
                "Successfully imported %s from configuration.yaml",
                import_data.get(CONF_HOST),
            )
        elif res["type"] == FlowResultType.FORM:
            _LOGGER.error(
                "Could not import %s from configuration.yaml",
                import_data.get(CONF_HOST),
            )
        return res

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
        yamaha = self.hass.data[DOMAIN][self.config_entry.entry_id]
        inputs = await self.hass.async_add_executor_job(yamaha.inputs)

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
