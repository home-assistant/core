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

from .const import CONF_ALLOW_NAMELESS_UUIDS, CONF_ALLOWED_BEACONS, DOMAIN


def _normalize_allowed_beacon(value: str) -> str:
    """Normalize an allowlisted beacon ID to `uuid_major_minor` format."""
    parts = value.strip().split("_")
    if len(parts) != 3:
        raise ValueError

    uuid_part, major_part, minor_part = (part.strip() for part in parts)
    normalized_uuid = str(UUID(uuid_part))
    major = int(major_part)
    minor = int(minor_part)

    if not (0 <= major <= 65535 and 0 <= minor <= 65535):
        raise ValueError

    return f"{normalized_uuid}_{major}_{minor}"


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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        current_uuids = list(
            self.config_entry.options.get(CONF_ALLOW_NAMELESS_UUIDS, [])
        )
        current_beacons = list(self.config_entry.options.get(CONF_ALLOWED_BEACONS, []))
        new_uuid: str | None = None
        new_allowed_beacon: str | None = None

        if user_input is not None:
            if new_uuid := user_input.get("new_uuid", "").lower():
                try:
                    # accept non-standard formats that can be fixed by UUID
                    new_uuid = str(UUID(new_uuid))
                except ValueError:
                    errors["new_uuid"] = "invalid_uuid_format"

            if new_allowed_beacon := user_input.get("new_allowed_beacon", ""):
                try:
                    new_allowed_beacon = _normalize_allowed_beacon(new_allowed_beacon)
                except ValueError:
                    errors["new_allowed_beacon"] = "invalid_beacon_id_format"

            if not errors:
                # don't modify current_uuids in memory, cause HA will think that the new
                # data is equal to the old, and will refuse to write them to disk.
                updated_uuids = list(
                    user_input.get(CONF_ALLOW_NAMELESS_UUIDS, current_uuids)
                )
                if new_uuid and new_uuid not in updated_uuids:
                    updated_uuids.append(new_uuid)

                updated_beacons = list(
                    user_input.get(CONF_ALLOWED_BEACONS, current_beacons)
                )
                if new_allowed_beacon and new_allowed_beacon not in updated_beacons:
                    updated_beacons.append(new_allowed_beacon)

                data: dict[str, list[str]] = {}
                if (
                    updated_uuids
                    or CONF_ALLOW_NAMELESS_UUIDS in user_input
                    or current_uuids
                ):
                    data[CONF_ALLOW_NAMELESS_UUIDS] = updated_uuids
                if (
                    updated_beacons
                    or CONF_ALLOWED_BEACONS in user_input
                    or current_beacons
                ):
                    data[CONF_ALLOWED_BEACONS] = updated_beacons

                return self.async_create_entry(title="", data=data)

        schema: VolDictType = {
            vol.Optional(
                "new_uuid",
                description={"suggested_value": new_uuid},
            ): str,
            vol.Optional(
                "new_allowed_beacon",
                description={"suggested_value": new_allowed_beacon},
            ): str,
        }
        if current_uuids:
            schema |= {
                vol.Optional(
                    CONF_ALLOW_NAMELESS_UUIDS,
                    default=current_uuids,
                ): cv.multi_select(sorted(current_uuids))
            }
        if current_beacons:
            schema |= {
                vol.Optional(
                    CONF_ALLOWED_BEACONS,
                    default=current_beacons,
                ): cv.multi_select(sorted(current_beacons))
            }
        return self.async_show_form(
            step_id="init", errors=errors, data_schema=vol.Schema(schema)
        )
