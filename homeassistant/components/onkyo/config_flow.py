"""Config flow for Onkyo."""

from collections import OrderedDict
from dataclasses import dataclass
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
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import receiver as rcver
from .const import (
    BRAND_NAME,
    CONF_SOURCES_ALLOWED,
    CONF_SOURCES_DEFAULT,
    CONF_VOLUME_RESOLUTION,
    CONF_VOLUME_RESOLUTION_DEFAULT,
    DOMAIN,
    OPTION_MAX_VOLUME,
    OPTION_MAX_VOLUME_DEFAULT,
    OPTION_SOURCE_PREFIX,
    OPTION_SOURCES,
)

CONF_SCHEMA_CONFIGURE = vol.Schema(
    {
        vol.Required(
            CONF_VOLUME_RESOLUTION,
            default=CONF_VOLUME_RESOLUTION_DEFAULT,
        ): vol.In([50, 80, 100, 200]),
        vol.Required(
            OPTION_SOURCES, default=list(CONF_SOURCES_DEFAULT.keys())
        ): SelectSelector(
            SelectSelectorConfig(
                options=CONF_SOURCES_ALLOWED,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReceiverConfig:
    """Onkyo Receiver configuration."""

    volume_resolution: int
    sources: dict[str, str]


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_infos: dict[str, rcver.Receiver] = {}
        self._receiver_info: rcver.ReceiverInfo

    def _createOnkyoEntry(self, config: ReceiverConfig, options=None):
        return self.async_create_entry(
            title=self._receiver_info.model_name,
            data={
                CONF_HOST: self._receiver_info.host,
                CONF_VOLUME_RESOLUTION: config.volume_resolution,
            },
            options={
                OPTION_MAX_VOLUME: OPTION_MAX_VOLUME_DEFAULT,
                OPTION_SOURCES: config.sources,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        return self.async_show_menu(
            step_id="user", menu_options=["eiscp_discovery", "manual"]
        )

    async def async_step_eiscp_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to discover devices."""

        if user_input is not None:
            self._receiver_info = self._discovered_infos[user_input[CONF_DEVICE]]
            return await self.async_step_configure_receiver()

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }

        infos = await rcver.async_discover()
        _LOGGER.debug("Discovered devices: %s", infos)

        self._discovered_infos = {}
        devices_names = {}
        for info in infos:
            self._discovered_infos[info.identifier] = info
            if (
                info.identifier not in current_unique_ids
                and info.host not in current_hosts
            ):
                devices_names[info.identifier] = (
                    f"{BRAND_NAME} {info.model_name} ({info.host}:{info.port})"
                )

        # Check if there is at least one device
        if not devices_names:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="eiscp_discovery",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_names)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device entry."""
        errors = {}

        if user_input is not None:
            info: rcver.ReceiverInfo | None
            host = user_input[CONF_HOST]
            try:
                info = await rcver.async_interview(host)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if info is not None:
                self._receiver_info = info
                return await self.async_step_configure_receiver()

            if "base" not in errors:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_configure_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration of a single receiver."""

        if user_input is not None:
            return self._createOnkyoEntry(
                ReceiverConfig(
                    user_input[CONF_VOLUME_RESOLUTION],
                    # Preseed the sources with a dictionary where keys and values are equal.
                    dict(
                        zip(
                            user_input[OPTION_SOURCES],
                            user_input[OPTION_SOURCES],
                            strict=False,
                        )
                    ),
                )
            )

        unique_id = f"{self._receiver_info.model_name}_{self._receiver_info.identifier}"
        _LOGGER.debug(
            "Found receiver with ip %s, setting unique_id to %s",
            self._receiver_info.host,
            unique_id,
        )
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._receiver_info.host}
        )

        return self.async_show_form(
            step_id="configure_receiver",
            description_placeholders={
                "name": f"{self._receiver_info.model_name} ({self._receiver_info.host})"
            },
            data_schema=CONF_SCHEMA_CONFIGURE,
        )

    # async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
    #     """Import the yaml config."""
    #     host: str = user_input[CONF_HOST]

    #     info = None
    #     try:
    #         info = await rcver.async_interview(host)
    #     except Exception:
    #         _LOGGER.exception("Unexpected exception")
    #         return self.async_abort(reason="cannot_connect")

    #     if info is None:
    #         # Info is None when connection fails
    #         return self.async_abort(reason="cannot_connect")

    #     await self.async_set_unique_id(info.identifier, raise_on_progress=False)
    #     self._abort_if_unique_id_configured()

    #     # TEDOEN: validate the user yaml: volume_resolution and sources

    #     return self._createOnkyoEntry(
    #         info,
    #         options={
    #             CONF_MAX_VOLUME: user_input[CONF_MAX_VOLUME],
    #             CONF_VOLUME_RESOLUTION: user_input[CONF_RECEIVER_MAX_VOLUME],
    #             CONF_SOURCES: user_input[CONF_SOURCES],
    #         },
    #     )

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

        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                data={
                    OPTION_MAX_VOLUME: user_input[OPTION_MAX_VOLUME],
                    # Unfold the source dictionary from the settings list
                    OPTION_SOURCES: {
                        key[len(OPTION_SOURCE_PREFIX) :]: value
                        for (key, value) in user_input.items()
                        if key.startswith(OPTION_SOURCE_PREFIX)
                    },
                }
            )

        schema: dict[str, Any] = OrderedDict()
        schema[
            vol.Required(
                OPTION_MAX_VOLUME,
                default=self.config_entry.options.get(OPTION_MAX_VOLUME),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)
        )

        # Handle options for sources selected at configuration.
        sources = self.config_entry.options.get(OPTION_SOURCES)
        if sources is not None:
            for source in sources:
                schema[
                    vol.Optional(
                        f"{OPTION_SOURCE_PREFIX}{source}", default=sources[source]
                    )
                ] = TextSelector()

        options_schema = vol.Schema(schema)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                options_schema, self.config_entry.options
            ),
        )
