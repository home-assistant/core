"""Config flow for Onkyo."""

import logging
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_RECEIVER_MAX_VOLUME,
    CONF_SOURCES,
    DOMAIN,
    OPTION_INPUT_SOURCES,
    OPTION_MAX_VOLUME,
    OPTION_MAX_VOLUME_DEFAULT,
    OPTION_VOLUME_RESOLUTION,
    OPTION_VOLUME_RESOLUTION_DEFAULT,
    VOLUME_RESOLUTION_ALLOWED,
    InputSource,
)
from .receiver import ReceiverInfo, async_discover, async_interview

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"

INPUT_SOURCES_ALL_MEANINGS = [
    input_source.value_meaning for input_source in InputSource
]
STEP_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
STEP_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(OPTION_VOLUME_RESOLUTION): vol.In(VOLUME_RESOLUTION_ALLOWED),
    }
)
STEP_CONFIGURE_SCHEMA = STEP_RECONFIGURE_SCHEMA.extend(
    {
        vol.Required(OPTION_INPUT_SOURCES): SelectSelector(
            SelectSelectorConfig(
                options=INPUT_SOURCES_ALL_MEANINGS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    _receiver_info: ReceiverInfo
    _discovered_infos: dict[str, ReceiverInfo]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user", menu_options=["manual", "eiscp_discovery"]
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device entry."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            _LOGGER.debug("Config flow start manual: %s", host)
            try:
                info = await async_interview(host)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if info is None:
                    errors["base"] = "cannot_connect"
                else:
                    self._receiver_info = info

                    await self.async_set_unique_id(
                        info.identifier, raise_on_progress=False
                    )
                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                    else:
                        self._abort_if_unique_id_configured()

                    return await self.async_step_configure_receiver()

        suggested_values = user_input
        if suggested_values is None and self.source == SOURCE_RECONFIGURE:
            suggested_values = {
                CONF_HOST: self._get_reconfigure_entry().data[CONF_HOST]
            }

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_MANUAL_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_eiscp_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start eiscp discovery and handle user device selection."""
        if user_input is not None:
            self._receiver_info = self._discovered_infos[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(
                self._receiver_info.identifier, raise_on_progress=False
            )
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._receiver_info.host}
            )
            return await self.async_step_configure_receiver()

        _LOGGER.debug("Config flow start eiscp discovery")

        try:
            infos = await async_discover()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        _LOGGER.debug("Discovered devices: %s", infos)

        self._discovered_infos = {}
        discovered_names = {}
        current_unique_ids = self._async_current_ids()
        for info in infos:
            if info.identifier in current_unique_ids:
                continue
            self._discovered_infos[info.identifier] = info
            device_name = f"{info.model_name} ({info.host})"
            discovered_names[info.identifier] = device_name

        _LOGGER.debug("Discovered new devices: %s", self._discovered_infos)

        if not discovered_names:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="eiscp_discovery",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE): vol.In(discovered_names)}
            ),
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle flow initialized by SSDP discovery."""
        _LOGGER.debug("Config flow start ssdp: %s", discovery_info)

        if udn := discovery_info.ssdp_udn:
            udn_parts = udn.split(":")
            if len(udn_parts) == 2:
                uuid = udn_parts[1]
                last_uuid_section = uuid.split("-")[-1].upper()
                await self.async_set_unique_id(last_uuid_section)
                self._abort_if_unique_id_configured()

        if discovery_info.ssdp_location is None:
            _LOGGER.error("SSDP location is None")
            return self.async_abort(reason="unknown")

        host = URL(discovery_info.ssdp_location).host

        if host is None:
            _LOGGER.error("SSDP host is None")
            return self.async_abort(reason="unknown")

        try:
            info = await async_interview(host)
        except OSError:
            _LOGGER.exception("Unexpected exception interviewing host %s", host)
            return self.async_abort(reason="unknown")

        if info is None:
            _LOGGER.debug("SSDP eiscp is None: %s", host)
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(info.identifier)
        self._abort_if_unique_id_configured(updates={CONF_HOST: info.host})

        self._receiver_info = info

        title_string = f"{info.model_name} ({info.host})"
        self.context["title_placeholders"] = {"name": title_string}
        return await self.async_step_configure_receiver()

    async def async_step_configure_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration of a single receiver."""
        errors = {}

        reconfigure_entry = None
        schema = STEP_CONFIGURE_SCHEMA
        if self.source == SOURCE_RECONFIGURE:
            schema = STEP_RECONFIGURE_SCHEMA
            reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            volume_resolution = user_input[OPTION_VOLUME_RESOLUTION]

            if reconfigure_entry is not None:
                entry_options = reconfigure_entry.options
                result = self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_HOST: self._receiver_info.host,
                    },
                    options={
                        OPTION_VOLUME_RESOLUTION: volume_resolution,
                        OPTION_MAX_VOLUME: entry_options[OPTION_MAX_VOLUME],
                        OPTION_INPUT_SOURCES: entry_options[OPTION_INPUT_SOURCES],
                    },
                )

                _LOGGER.debug("Reconfigured receiver, result: %s", result)
                return result

            input_source_meanings: list[str] = user_input[OPTION_INPUT_SOURCES]
            if not input_source_meanings:
                errors[OPTION_INPUT_SOURCES] = "empty_input_source_list"
            else:
                input_sources_store: dict[str, str] = {}
                for input_source_meaning in input_source_meanings:
                    input_source = InputSource.from_meaning(input_source_meaning)
                    input_sources_store[input_source.value] = input_source_meaning

                result = self.async_create_entry(
                    title=self._receiver_info.model_name,
                    data={
                        CONF_HOST: self._receiver_info.host,
                    },
                    options={
                        OPTION_VOLUME_RESOLUTION: volume_resolution,
                        OPTION_MAX_VOLUME: OPTION_MAX_VOLUME_DEFAULT,
                        OPTION_INPUT_SOURCES: input_sources_store,
                    },
                )

                _LOGGER.debug("Configured receiver, result: %s", result)
                return result

        _LOGGER.debug("Configuring receiver, info: %s", self._receiver_info)

        suggested_values = user_input
        if suggested_values is None:
            if reconfigure_entry is None:
                suggested_values = {
                    OPTION_VOLUME_RESOLUTION: OPTION_VOLUME_RESOLUTION_DEFAULT,
                    OPTION_INPUT_SOURCES: [],
                }
            else:
                entry_options = reconfigure_entry.options
                suggested_values = {
                    OPTION_VOLUME_RESOLUTION: entry_options[OPTION_VOLUME_RESOLUTION],
                    OPTION_INPUT_SOURCES: [
                        InputSource(input_source).value_meaning
                        for input_source in entry_options[OPTION_INPUT_SOURCES]
                    ],
                }

        return self.async_show_form(
            step_id="configure_receiver",
            data_schema=self.add_suggested_values_to_schema(schema, suggested_values),
            errors=errors,
            description_placeholders={
                "name": f"{self._receiver_info.model_name} ({self._receiver_info.host})"
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the receiver."""
        return await self.async_step_manual()

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        _LOGGER.debug("Import flow user input: %s", user_input)

        host: str = user_input[CONF_HOST]
        name: str | None = user_input.get(CONF_NAME)
        user_max_volume: int = user_input[OPTION_MAX_VOLUME]
        user_volume_resolution: int = user_input[CONF_RECEIVER_MAX_VOLUME]
        user_sources: dict[InputSource, str] = user_input[CONF_SOURCES]

        info: ReceiverInfo | None = user_input.get("info")
        if info is None:
            try:
                info = await async_interview(host)
            except Exception:
                _LOGGER.exception("Import flow interview error for host %s", host)
                return self.async_abort(reason="cannot_connect")

        if info is None:
            _LOGGER.error("Import flow interview error for host %s", host)
            return self.async_abort(reason="cannot_connect")

        unique_id = info.identifier
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        name = name or info.model_name

        volume_resolution = VOLUME_RESOLUTION_ALLOWED[-1]
        for volume_resolution_allowed in VOLUME_RESOLUTION_ALLOWED:
            if user_volume_resolution <= volume_resolution_allowed:
                volume_resolution = volume_resolution_allowed
                break

        max_volume = min(
            100, user_max_volume * user_volume_resolution / volume_resolution
        )

        sources_store: dict[str, str] = {}
        for source, source_name in user_sources.items():
            sources_store[source.value] = source_name

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
            },
            options={
                OPTION_VOLUME_RESOLUTION: volume_resolution,
                OPTION_MAX_VOLUME: max_volume,
                OPTION_INPUT_SOURCES: sources_store,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return OnkyoOptionsFlowHandler()


OPTIONS_STEP_INIT_SCHEMA = vol.Schema(
    {
        vol.Required(OPTION_MAX_VOLUME): NumberSelector(
            NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(OPTION_INPUT_SOURCES): SelectSelector(
            SelectSelectorConfig(
                options=INPUT_SOURCES_ALL_MEANINGS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class OnkyoOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Onkyo."""

    _data: dict[str, Any]
    _input_sources: dict[InputSource, str]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}

        entry_options = self.config_entry.options

        if user_input is not None:
            self._input_sources = {}
            for input_source_meaning in user_input[OPTION_INPUT_SOURCES]:
                input_source = InputSource.from_meaning(input_source_meaning)
                input_source_name = entry_options[OPTION_INPUT_SOURCES].get(
                    input_source.value, input_source_meaning
                )
                self._input_sources[input_source] = input_source_name

            if not self._input_sources:
                errors[OPTION_INPUT_SOURCES] = "empty_input_source_list"
            else:
                self._data = {
                    OPTION_VOLUME_RESOLUTION: entry_options[OPTION_VOLUME_RESOLUTION],
                    OPTION_MAX_VOLUME: user_input[OPTION_MAX_VOLUME],
                }

                return await self.async_step_names()

        suggested_values = user_input
        if suggested_values is None:
            suggested_values = {
                OPTION_MAX_VOLUME: entry_options[OPTION_MAX_VOLUME],
                OPTION_INPUT_SOURCES: [
                    InputSource(input_source).value_meaning
                    for input_source in entry_options[OPTION_INPUT_SOURCES]
                ],
            }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_STEP_INIT_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure names."""
        if user_input is not None:
            input_sources_store: dict[str, str] = {}
            for input_source_meaning, input_source_name in user_input[
                "input_sources"
            ].items():
                input_source = InputSource.from_meaning(input_source_meaning)
                input_sources_store[input_source.value] = input_source_name

            return self.async_create_entry(
                data={
                    **self._data,
                    OPTION_INPUT_SOURCES: input_sources_store,
                }
            )

        schema_dict: dict[Any, Selector] = {}

        for input_source, input_source_name in self._input_sources.items():
            schema_dict[
                vol.Required(input_source.value_meaning, default=input_source_name)
            ] = TextSelector()

        return self.async_show_form(
            step_id="names",
            data_schema=vol.Schema(
                {vol.Required("input_sources"): section(vol.Schema(schema_dict))}
            ),
        )
