"""Config flow for Immich Frames."""

from typing import Any, override

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_FRAME_NAME, CONF_IMMICH_ENTRY_ID, DOMAIN


class ImmichFramesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of a frame linked to an Immich account."""

    VERSION = 1

    @staticmethod
    @override
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return ImmichFramesOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an existing Immich account and name the frame."""
        immich_entries = self.hass.config_entries.async_entries("immich")
        if not immich_entries:
            return self.async_abort(reason="immich_required")

        errors: dict[str, str] = {}
        if user_input is not None:
            immich_entry_id = user_input[CONF_IMMICH_ENTRY_ID]
            if not any(entry.entry_id == immich_entry_id for entry in immich_entries):
                errors["base"] = "immich_unavailable"
            elif not user_input[CONF_FRAME_NAME].strip():
                errors[CONF_FRAME_NAME] = "name_required"
            else:
                frame_name = user_input[CONF_FRAME_NAME].strip()
                await self.async_set_unique_id(f"{immich_entry_id}|{frame_name}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=frame_name,
                    data={
                        CONF_IMMICH_ENTRY_ID: immich_entry_id,
                        CONF_FRAME_NAME: frame_name,
                    },
                )

        options = [
            SelectOptionDict(value=entry.entry_id, label=entry.title)
            for entry in immich_entries
            if entry.state is ConfigEntryState.LOADED
        ]
        if not options:
            return self.async_abort(reason="immich_not_ready")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_IMMICH_ENTRY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Required(CONF_FRAME_NAME): str,
                }
            ),
            errors=errors,
        )


class ImmichFramesOptionsFlow(config_entries.OptionsFlow):
    """Configure frame-specific options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Keep the first Core slice intentionally option-free."""
        return self.async_create_entry(title="", data={})
