"""Config flow for Onkyo."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
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

from .const import (
    CONF_RECEIVER_MAX_VOLUME,
    CONF_VOLUME_RESOLUTION,
    CONF_VOLUME_RESOLUTION_DEFAULT,
    DOMAIN,
    OPTION_MAX_VOLUME,
    OPTION_MAX_VOLUME_DEFAULT,
    OPTION_SOURCE_PREFIX,
    OPTION_SOURCES,
    OPTION_SOURCES_ALLOWED,
    VOLUME_RESOLUTION_ALLOWED,
    InputSource,
)
from .receiver import ReceiverInfo, async_discover, async_interview

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"

STEP_CONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_VOLUME_RESOLUTION,
            default=CONF_VOLUME_RESOLUTION_DEFAULT,
        ): vol.In(VOLUME_RESOLUTION_ALLOWED),
        vol.Required(OPTION_SOURCES, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=OPTION_SOURCES_ALLOWED,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=OPTION_SOURCES,
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
                    self._abort_if_unique_id_configured(updates=user_input)
                    return await self.async_step_configure_receiver()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
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

    async def async_step_configure_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration of a single receiver."""
        errors = {}

        if user_input is not None:
            user_sources: list[str] = user_input[OPTION_SOURCES]
            if not user_sources:
                errors[OPTION_SOURCES] = "empty_source_list"
            else:
                sources_str: dict[str, str] = {}
                for value_str in user_sources:
                    # Remove the source prefix.
                    value = int(value_str[len(OPTION_SOURCE_PREFIX) :], 16)
                    source = InputSource(value)
                    source_name = ", ".join(source.value_meanings)
                    sources_str.setdefault(source.value_hex, source_name)

                result = self.async_create_entry(
                    title=self._receiver_info.model_name,
                    data={
                        CONF_HOST: self._receiver_info.host,
                        CONF_VOLUME_RESOLUTION: user_input[CONF_VOLUME_RESOLUTION],
                    },
                    options={
                        OPTION_MAX_VOLUME: OPTION_MAX_VOLUME_DEFAULT,
                        OPTION_SOURCES: sources_str,
                    },
                )
                _LOGGER.debug("Configured receiver, result: %s", result)
                return result

        _LOGGER.debug("Configuring receiver, info: %s", self._receiver_info)

        return self.async_show_form(
            step_id="configure_receiver",
            data_schema=STEP_CONFIGURE_SCHEMA,
            errors=errors,
            description_placeholders={
                "name": f"{self._receiver_info.model_name} ({self._receiver_info.host})"
            },
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        _LOGGER.debug("Import flow user input: %s", user_input)

        host: str = user_input[CONF_HOST]
        name: str | None = user_input.get(CONF_NAME)
        user_max_volume: int = user_input[OPTION_MAX_VOLUME]
        user_volume_resolution: int = user_input[CONF_RECEIVER_MAX_VOLUME]
        user_sources: dict[str, str] = user_input[OPTION_SOURCES]

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

        all_meanings = InputSource.all_meanings()
        sources_str: dict[str, str] = {}
        for meaning, source_name in user_sources.items():
            if meaning in all_meanings:
                source = InputSource.from_meaning(meaning)
                sources_str[source.value_hex] = source_name

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                CONF_VOLUME_RESOLUTION: volume_resolution,
            },
            options={
                OPTION_MAX_VOLUME: max_volume,
                OPTION_SOURCES: sources_str,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return OnkyoOptionsFlowHandler(config_entry)


class OnkyoOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle an options flow for Onkyo."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)

        sources_str: dict[str, str] = self.options[OPTION_SOURCES]
        sources = {InputSource(int(k, 16)): v for k, v in sources_str.items()}
        self.options[OPTION_SOURCES] = sources

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            sources_str: dict[str, str] = {}
            for value_str, source_name in user_input.items():
                if value_str.startswith(OPTION_SOURCE_PREFIX):
                    # Remove the source prefix.
                    value = int(value_str[len(OPTION_SOURCE_PREFIX) :], 16)
                    source = InputSource(value)
                    sources_str[source.value_hex] = source_name

            return self.async_create_entry(
                data={
                    OPTION_MAX_VOLUME: user_input[OPTION_MAX_VOLUME],
                    OPTION_SOURCES: sources_str,
                }
            )

        schema_dict: dict[Any, Selector] = {}

        max_volume: float = self.options[OPTION_MAX_VOLUME]
        schema_dict[vol.Required(OPTION_MAX_VOLUME, default=max_volume)] = (
            NumberSelector(
                NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)
            )
        )

        sources: dict[InputSource, str] = self.options[OPTION_SOURCES]
        for source in sources:
            # Add the source prefix.
            schema_dict[
                vol.Required(
                    f"{OPTION_SOURCE_PREFIX}{source.value_hex}", default=sources[source]
                )
            ] = TextSelector()

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
