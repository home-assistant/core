"""Config flow for Ness Alarm integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from nessclient import Client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ID,
    CONF_INFER_ARMING_STATE,
    CONF_MAX_SUPPORTED_ZONES,
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
)

_LOGGER = logging.getLogger(__name__)


class NessAlarmConfigError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NessAlarmConnectionError(HomeAssistantError):
    """Error to indicate connection failure."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    host = data[CONF_HOST]
    port = data[CONF_PORT]

    client = Client(host=host, port=port, update_interval=DEFAULT_SCAN_INTERVAL)

    try:
        keepalive_task = asyncio.create_task(client.keepalive())

        panel_info = await asyncio.wait_for(client.get_panel_info(), timeout=5.0)

        keepalive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive_task

        await client.close()

    except TimeoutError:
        _LOGGER.error("Timeout connecting to Ness Alarm at %s:%s", host, port)
        await client.close()
        raise NessAlarmConnectionError(f"Timeout connecting to {host}:{port}") from None
    except Exception as err:
        _LOGGER.error("Failed to connect to Ness Alarm: %s", err)
        await client.close()
        raise NessAlarmConnectionError(f"Cannot connect to {host}:{port}") from err
    else:
        return {
            "title": f"Ness Alarm {panel_info.model.value} ({host})",
            "model": panel_info.model.value,
            "version": panel_info.version,
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
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except NessAlarmConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(
                    CONF_MAX_SUPPORTED_ZONES, default=DEFAULT_MAX_SUPPORTED_ZONES
                ): int,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_float, vol.Range(min=0.1, max=3600)),
                vol.Optional(
                    CONF_INFER_ARMING_STATE, default=DEFAULT_INFER_ARMING_STATE
                ): bool,
                vol.Optional(
                    CONF_SUPPORT_HOME_ARM, default=DEFAULT_SUPPORT_HOME_ARM
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle import from YAML."""

        scan_interval = import_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if hasattr(scan_interval, "total_seconds"):
            scan_interval = int(scan_interval.total_seconds())

        zones = import_config.get(CONF_ZONES, [])
        if zones:
            zone_ids = [zone.get(CONF_ID, 0) for zone in zones]
            max_zone_id = max(zone_ids) if zone_ids else DEFAULT_MAX_SUPPORTED_ZONES
        else:
            max_zone_id = DEFAULT_MAX_SUPPORTED_ZONES

        data = {
            CONF_HOST: import_config[CONF_HOST],
            CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
            CONF_MAX_SUPPORTED_ZONES: max_zone_id,
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

        options = {
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_INFER_ARMING_STATE: import_config.get(
                CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE
            ),
        }

        try:
            info = await validate_input(self.hass, data)
            unique_id = f"{info['model']}_{data[CONF_HOST]}_{data[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data=data,
                options=options,
            )
        except NessAlarmConnectionError:
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
            return self.async_create_entry(title="", data=user_input)

        # Build options schema with current values
        current_scan = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_infer = entry.options.get(
            CONF_INFER_ARMING_STATE,
            entry.data.get(CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE),
        )
        current_home = entry.options.get(
            CONF_SUPPORT_HOME_ARM,
            entry.data.get(CONF_SUPPORT_HOME_ARM, DEFAULT_SUPPORT_HOME_ARM),
        )
        current_max_zones = entry.options.get(
            CONF_MAX_SUPPORTED_ZONES,
            entry.data.get(CONF_MAX_SUPPORTED_ZONES, DEFAULT_MAX_SUPPORTED_ZONES),
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_scan): vol.All(
                    cv.positive_int, vol.Range(min=1, max=3600)
                ),
                vol.Optional(CONF_INFER_ARMING_STATE, default=current_infer): bool,
                vol.Optional(CONF_SUPPORT_HOME_ARM, default=current_home): bool,
                vol.Optional(CONF_MAX_SUPPORTED_ZONES, default=current_max_zones): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
