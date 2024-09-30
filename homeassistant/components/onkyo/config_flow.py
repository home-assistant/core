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
    OPTION_SOURCES_DEFAULT,
)
from .receiver import ReceiverInfo, async_discover, async_interview

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"

STEP_CONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_VOLUME_RESOLUTION,
            default=CONF_VOLUME_RESOLUTION_DEFAULT,
        ): vol.In([50, 80, 100, 200]),
        vol.Required(
            OPTION_SOURCES, default=list(OPTION_SOURCES_DEFAULT.keys())
        ): SelectSelector(
            SelectSelectorConfig(
                options=OPTION_SOURCES_ALLOWED,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._receiver_info: ReceiverInfo
        self._discovered_infos: dict[str, ReceiverInfo] = {}

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
            info: ReceiverInfo | None = None
            host = user_input[CONF_HOST]
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
                    return await self.async_step_configure_receiver()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
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
            return await self.async_step_configure_receiver()

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }

        try:
            infos = await async_discover()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        _LOGGER.debug("Discovered devices: %s", infos)

        self._discovered_infos = {}
        devices_names = {}
        for info in infos:
            self._discovered_infos[info.identifier] = info
            if (
                info.identifier not in current_unique_ids
                and info.host not in current_hosts
            ):
                devices_names[info.identifier] = f"{info.model_name} ({info.host})"

        if not devices_names:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="eiscp_discovery",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_names)}),
        )

    async def async_step_configure_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration of a single receiver."""
        _LOGGER.debug("Configure receiver info: %s", self._receiver_info)

        if user_input is not None:
            return self.async_create_entry(
                title=self._receiver_info.model_name,
                data={
                    CONF_HOST: self._receiver_info.host,
                    CONF_VOLUME_RESOLUTION: user_input[CONF_VOLUME_RESOLUTION],
                },
                options={
                    OPTION_MAX_VOLUME: OPTION_MAX_VOLUME_DEFAULT,
                    # Preseed the sources with a dictionary where keys and values are equal.
                    OPTION_SOURCES: dict(
                        zip(
                            user_input[OPTION_SOURCES],
                            user_input[OPTION_SOURCES],
                            strict=False,
                        )
                    ),
                },
            )

        unique_id = self._receiver_info.identifier
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._receiver_info.host}
        )

        return self.async_show_form(
            step_id="configure_receiver",
            description_placeholders={
                "name": f"{self._receiver_info.model_name} ({self._receiver_info.host})"
            },
            data_schema=STEP_CONFIGURE_SCHEMA,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        _LOGGER.debug("Import flow user input: %s", user_input)

        host: str = user_input[CONF_HOST]
        name: str | None = user_input.get(CONF_NAME)
        max_volume: float = float(user_input[OPTION_MAX_VOLUME])
        volume_resolution: int = user_input[CONF_RECEIVER_MAX_VOLUME]
        sources: dict[str, str] = user_input[OPTION_SOURCES]

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
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        name = name or info.model_name

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                CONF_VOLUME_RESOLUTION: volume_resolution,
            },
            options={
                OPTION_MAX_VOLUME: max_volume,
                OPTION_SOURCES: sources,
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    OPTION_MAX_VOLUME: user_input[OPTION_MAX_VOLUME],
                    # Remove the source prefix.
                    OPTION_SOURCES: {
                        key[len(OPTION_SOURCE_PREFIX) :]: value
                        for (key, value) in user_input.items()
                        if key.startswith(OPTION_SOURCE_PREFIX)
                    },
                }
            )

        schema_dict: dict[Any, Selector] = {}

        max_volume: float = self.config_entry.options[OPTION_MAX_VOLUME]
        schema_dict[vol.Required(OPTION_MAX_VOLUME, default=max_volume)] = (
            NumberSelector(
                NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)
            )
        )

        sources: dict[str, str] = self.config_entry.options[OPTION_SOURCES]
        for source in sources:
            # Add the source prefix.
            schema_dict[
                vol.Required(f"{OPTION_SOURCE_PREFIX}{source}", default=sources[source])
            ] = TextSelector()

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
