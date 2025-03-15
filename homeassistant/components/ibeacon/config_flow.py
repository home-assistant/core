"""Config flow for iBeacon Tracker integration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import CONF_ALLOW_NAMELESS_UUIDS, DOMAIN


class IBeaconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iBeacon Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not bluetooth.async_scanner_count(self.hass, connectable=False):
            return self.async_abort(reason="bluetooth_not_available")

        if user_input is not None:
            return self.async_create_entry(title="iBeacon Tracker", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return IBeaconOptionsFlow()


class IBeaconOptionsFlow(OptionsFlow):
    """Handle options."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}

        current_uuids = self.config_entry.options.get(CONF_ALLOW_NAMELESS_UUIDS, [])
        new_uuid = None

        if user_input is not None:
            if new_uuid := user_input.get("new_uuid", "").lower():
                try:
                    # accept non-standard formats that can be fixed by UUID
                    new_uuid = str(UUID(new_uuid))
                except ValueError:
                    errors["new_uuid"] = "invalid_uuid_format"

            if not errors:
                # don't modify current_uuids in memory, cause HA will think that the new
                # data is equal to the old, and will refuse to write them to disk.
                updated_uuids = user_input.get("allow_nameless_uuids", [])
                if new_uuid and new_uuid not in updated_uuids:
                    updated_uuids.append(new_uuid)

                data = {CONF_ALLOW_NAMELESS_UUIDS: list(updated_uuids)}
                return self.async_create_entry(title="", data=data)

        schema: VolDictType = {
            vol.Optional(
                "new_uuid",
                description={"suggested_value": new_uuid},
            ): str,
        }
        if current_uuids:
            schema |= {
                vol.Optional(
                    "allow_nameless_uuids",
                    default=current_uuids,
                ): cv.multi_select(sorted(current_uuids))
            }
        return self.async_show_form(
            step_id="init", errors=errors, data_schema=vol.Schema(schema)
        )
