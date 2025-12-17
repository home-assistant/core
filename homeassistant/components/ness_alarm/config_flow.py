"""Config flow for Ness Alarm integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from nessclient import Client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ID,
    CONF_INFER_ARMING_STATE,
    CONF_NAME,
    CONF_SUPPORT_HOME_ARM,
    CONF_TYPE,
    CONF_ZONES,
    DEFAULT_INFER_ARMING_STATE,
    DEFAULT_MAX_SUPPORTED_ZONES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUPPORT_HOME_ARM,
    DOMAIN,
    PANEL_MODEL_ZONES,
)

_LOGGER = logging.getLogger(__name__)


class NessAlarmConfigError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NessAlarmConnectionError(HomeAssistantError):
    """Error to indicate connection failure."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and get panel info."""

    host = data[CONF_HOST]
    port = data[CONF_PORT]

    client = Client(host=host, port=port, update_interval=DEFAULT_SCAN_INTERVAL)

    try:
        keepalive_task = asyncio.create_task(client.keepalive())

        # Try to get panel info
        panel_info = await asyncio.wait_for(client.get_panel_info(), timeout=5.0)

        keepalive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive_task

    except TimeoutError:
        _LOGGER.error("Timeout connecting to Ness Alarm at %s:%s", host, port)
        raise NessAlarmConnectionError(f"Timeout connecting to {host}:{port}") from None
    except Exception as err:
        _LOGGER.error("Failed to connect to Ness Alarm: %s", err)
        raise NessAlarmConnectionError(f"Cannot connect to {host}:{port}") from err
    finally:
        await client.close()

    # process panel info after successful connection
    panel_model = panel_info.model.value if panel_info else "UNKNOWN"

    # Log the detected model and its zone capacity
    if panel_model in PANEL_MODEL_ZONES:
        zone_count = PANEL_MODEL_ZONES[panel_model]
        _LOGGER.debug(
            "Detected panel model %s with %s zone capacity",
            panel_model,
            zone_count,
        )
    else:
        _LOGGER.debug(
            "Unknown panel model %s, will default to %s zones enabled",
            panel_model,
            DEFAULT_MAX_SUPPORTED_ZONES,
        )

    return {
        "title": f"Ness Alarm {panel_model} ({host})",
        "model": panel_model,
        "version": panel_info.version if panel_info else None,
    }


class NessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ness Alarm."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate the connection and fetch model/version
                info = await validate_input(self.hass, user_input)
            except NessAlarmConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._async_abort_entries_match(
                    {
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )

                user_input["panel_model"] = info["model"]

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(
                    CONF_INFER_ARMING_STATE, default=DEFAULT_INFER_ARMING_STATE
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle import from YAML."""

        data = {
            CONF_HOST: import_config[CONF_HOST],
            CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
        }

        zones = import_config.get(CONF_ZONES, [])

        options = {
            CONF_INFER_ARMING_STATE: import_config.get(
                CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE
            ),
        }

        if zones:
            data[CONF_ZONES] = [
                {
                    CONF_ID: zone.get(CONF_ID),
                    CONF_NAME: zone.get(CONF_NAME),
                    CONF_TYPE: zone.get(CONF_TYPE, "motion"),
                }
                for zone in zones
                if zone.get(CONF_ID) and zone.get(CONF_NAME)
            ]

        try:
            info = await validate_input(self.hass, data)

            self._async_abort_entries_match(
                {
                    CONF_HOST: data[CONF_HOST],
                    CONF_PORT: data[CONF_PORT],
                }
            )

            data["panel_model"] = info["model"]

            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"yaml_imported_{data[CONF_HOST]}_{data[CONF_PORT]}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="yaml_config_imported",
                translation_placeholders={
                    "host": data[CONF_HOST],
                    "port": str(data[CONF_PORT]),
                    "panel_model": info["model"],
                    "panel_version": info["version"],
                    "zone_count": str(
                        PANEL_MODEL_ZONES.get(
                            info["model"], DEFAULT_MAX_SUPPORTED_ZONES
                        )
                    ),
                },
            )

            return self.async_create_entry(
                title=info["title"],
                data=data,
                options=options,
            )

        except NessAlarmConnectionError:
            # Can't connect - create error issue about failed import
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"yaml_import_failed_{data[CONF_HOST]}_{data[CONF_PORT]}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="yaml_import_failed",
                translation_placeholders={
                    "host": data[CONF_HOST],
                    "port": str(data[CONF_PORT]),
                    "yaml_example": f"ness_alarm:\n  host: {data[CONF_HOST]}\n  port: {data[CONF_PORT]}",
                },
            )
            return self.async_abort(reason="cannot_connect")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Ness Alarm."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry_id = config_entry.entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            # Update the config entry data with new zone count if changed
            if "enabled_zones" in user_input:
                new_data = dict(entry.data)
                # Map the zone count to a panel model for consistency
                zone_count = user_input["enabled_zones"]
                new_data["panel_model"] = (
                    f"MANUAL_{zone_count if zone_count in (8, 16, 24) else DEFAULT_MAX_SUPPORTED_ZONES}"
                )

                self.hass.config_entries.async_update_entry(entry, data=new_data)

                # Remove enabled_zones from options as it's stored in data
                options = dict(user_input)
                options.pop("enabled_zones", None)
                return self.async_create_entry(title="", data=options)

            return self.async_create_entry(title="", data=user_input)

        # Build options schema with current values
        current_infer = entry.options.get(
            CONF_INFER_ARMING_STATE,
            entry.data.get(CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE),
        )
        current_home = entry.options.get(
            CONF_SUPPORT_HOME_ARM,
            entry.data.get(CONF_SUPPORT_HOME_ARM, DEFAULT_SUPPORT_HOME_ARM),
        )

        # Get current zone count from panel model
        panel_model = entry.data.get("panel_model", "UNKNOWN")
        current_zones = PANEL_MODEL_ZONES.get(panel_model, DEFAULT_MAX_SUPPORTED_ZONES)

        schema = vol.Schema(
            {
                vol.Optional(CONF_INFER_ARMING_STATE, default=current_infer): bool,
                vol.Optional(CONF_SUPPORT_HOME_ARM, default=current_home): bool,
                vol.Optional("enabled_zones", default=current_zones): vol.In(
                    {8: "8 zones", 16: "16 zones", 24: "24 zones", 32: "32 zones"}
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
