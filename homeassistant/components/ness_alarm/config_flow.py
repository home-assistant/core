"""Config flow for Ness Alarm integration."""

from __future__ import annotations

import logging
import socket
from typing import Any

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
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    def test_connection():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex((host, port))
        except OSError:
            return False
        else:
            return result == 0
        finally:
            sock.close()

    is_connected = await hass.async_add_executor_job(test_connection)

    if not is_connected:
        raise NessAlarmConnectionError(f"Cannot connect to {host}:{port}")

    return {"title": f"Ness Alarm ({host})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ness Alarm."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Set unique ID
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
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Range(min=1, max=3600)),
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
        scan_interval = import_config.get(CONF_SCAN_INTERVAL)
        if scan_interval and hasattr(scan_interval, "total_seconds"):
            scan_interval = int(scan_interval.total_seconds())

        zones = import_config.get(CONF_ZONES, [])

        if zones:
            zone_ids = [zone.get(CONF_ID, 0) for zone in zones]
            if zone_ids:
                max_zone_id = max(zone_ids)
            else:
                max_zone_id = DEFAULT_MAX_SUPPORTED_ZONES
        else:
            max_zone_id = import_config.get(
                CONF_MAX_SUPPORTED_ZONES, DEFAULT_MAX_SUPPORTED_ZONES
            )

        data = {
            CONF_HOST: import_config[CONF_HOST],
            CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
            CONF_SCAN_INTERVAL: scan_interval or DEFAULT_SCAN_INTERVAL,
            CONF_INFER_ARMING_STATE: import_config.get(
                CONF_INFER_ARMING_STATE, DEFAULT_INFER_ARMING_STATE
            ),
            CONF_SUPPORT_HOME_ARM: import_config.get(
                CONF_SUPPORT_HOME_ARM, DEFAULT_SUPPORT_HOME_ARM
            ),
            CONF_MAX_SUPPORTED_ZONES: max_zone_id,
            CONF_ZONES: [
                {
                    CONF_ID: zone.get(CONF_ID),
                    CONF_NAME: zone.get(CONF_NAME),
                    CONF_TYPE: zone.get(CONF_TYPE, "motion"),
                }
                for zone in zones
                if zone.get(CONF_ID) and zone.get(CONF_NAME)
            ],
        }
        await self.async_set_unique_id(f"{data[CONF_HOST]}:{data[CONF_PORT]}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Ness Alarm ({data[CONF_HOST]})", data=data
        )

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
        # Fetch the config entry dynamically
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
