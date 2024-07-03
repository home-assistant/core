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
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import ObjectSelector

from . import receiver as rcver
from .const import (
    BRAND_NAME,
    CONF_DEVICE,
    CONF_MAX_VOLUME,
    CONF_MAX_VOLUME_DEFAULT,
    CONF_RECEIVER_MAX_VOLUME,
    CONF_SOURCES,
    CONF_SOURCES_DEFAULT,
    CONF_VOLUME_RESOLUTION,
    CONF_VOLUME_RESOLUTION_DEFAULT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_infos: dict[str, rcver.Receiver] = {}

    def _createOnkyoEntry(self, info: rcver.ReceiverInfo, options=None):
        return self.async_create_entry(
            title=info.model_name,
            data={
                CONF_HOST: info.host,
            },
            options=options,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        return self.async_show_menu(
            step_id="user", menu_options=["pick_device", "manual"]
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device entry."""
        errors = {}

        if user_input is not None:
            info = None
            try:
                info = await rcver.async_interview(user_input[CONF_HOST])
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if info is not None:
                await self.async_set_unique_id(info.identifier, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self._createOnkyoEntry(info)

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

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to discover or pick discovered device."""

        if user_input is not None:
            info = self._discovered_infos[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(info.identifier, raise_on_progress=False)

            return self._createOnkyoEntry(info)

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        infos = await rcver.async_discover()

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
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_names)}),
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        host: str = user_input[CONF_HOST]

        info = None
        try:
            info = await rcver.async_interview(host)
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="cannot_connect")

        if info is None:
            # Info is None when connection fails
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(info.identifier, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        # TODO: validate the user yaml: volume_resolution and sources

        return self._createOnkyoEntry(
            info,
            options={
                CONF_MAX_VOLUME: user_input[CONF_MAX_VOLUME],
                CONF_VOLUME_RESOLUTION: user_input[CONF_RECEIVER_MAX_VOLUME],
                CONF_SOURCES: user_input[CONF_SOURCES],
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
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                SCHEMA_SOURCES = vol.Schema({str: str})
                SCHEMA_SOURCES(user_input.get(CONF_SOURCES))
            except vol.error.Invalid:
                errors["base"] = "invalid_sources"

            if not errors:
                return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_MAX_VOLUME, default=CONF_MAX_VOLUME_DEFAULT): vol.All(
                    cv.positive_int, vol.Range(min=0, max=100)
                ),
                vol.Required(
                    CONF_VOLUME_RESOLUTION,
                    default=CONF_VOLUME_RESOLUTION_DEFAULT,
                ): vol.All(cv.positive_int, vol.Range(min=0, max=200)),
                vol.Required(
                    CONF_SOURCES, default=CONF_SOURCES_DEFAULT
                ): ObjectSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                options_schema, self.config_entry.options
            ),
        )
