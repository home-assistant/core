"""Config flow and options flow for Mertik Maxitrol fireplace."""

import logging
import socket
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.components.sensor import SensorDeviceClass

from .const import (
    DOMAIN,
    CONF_LOW_THRESHOLD,
    CONF_HIGH_THRESHOLD,
    CONF_TEMP_SENSOR,
    CONF_TEMP_STEP,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_TEMP_SENSOR,
    DEFAULT_TEMP_STEP,
)

_LOGGER = logging.getLogger(__name__)


def _temp_sensor_options(hass: HomeAssistant) -> dict[str, str]:
    """Return {entity_id: friendly_name} for all temperature sensors."""
    registry = er.async_get(hass)
    options = {"": "Mertik handset (built-in)"}
    for entry in registry.entities.values():
        state = hass.states.get(entry.entity_id)
        if state is None:
            continue
        if state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE:
            # Skip the Mertik's own sensor to avoid it appearing twice
            if entry.domain == "sensor" and entry.platform == DOMAIN:
                continue
            friendly = state.attributes.get("friendly_name", entry.entity_id)
            options[entry.entity_id] = f"{friendly} ({entry.entity_id})"
    return options


class MertikConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup: name, host, thresholds."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            low = user_input.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)
            high = user_input.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)

            if low <= 0 or high <= 0 or low >= high:
                errors["base"] = "invalid_thresholds"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                can_connect = await self.hass.async_add_executor_job(
                    _test_connection, host
                )
                if not can_connect:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="Mertik Maxitrol", data=user_input
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Optional(
                    CONF_LOW_THRESHOLD, default=DEFAULT_LOW_THRESHOLD
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_HIGH_THRESHOLD, default=DEFAULT_HIGH_THRESHOLD
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            low = user_input.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)
            high = user_input.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)

            if low <= 0 or high <= 0 or low >= high:
                errors["base"] = "invalid_thresholds"
            else:
                can_connect = await self.hass.async_add_executor_job(
                    _test_connection, host
                )
                if not can_connect:
                    errors["base"] = "cannot_connect"
                else:
                    existing = (
                        self.hass.config_entries.async_entry_for_domain_unique_id(
                            DOMAIN, host
                        )
                    )
                    if existing and existing.entry_id != entry.entry_id:
                        errors["base"] = "already_configured"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            unique_id=host,
                            data_updates=user_input,
                        )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=entry.data.get(CONF_NAME, "")): str,
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_LOW_THRESHOLD,
                    default=entry.data.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_HIGH_THRESHOLD,
                    default=entry.data.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD),
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "MertikOptionsFlow":
        return MertikOptionsFlow(config_entry)


class MertikOptionsFlow(config_entries.OptionsFlow):
    """Options flow: adjust thresholds and temperature sensor selection.

    Accessible via Settings -> Devices & Services -> Mertik -> Configure.
    Changes take effect immediately without restarting HA.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        # Current values (prefer options over data for previously set values)
        current_low = self._entry.options.get(
            CONF_LOW_THRESHOLD,
            self._entry.data.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD),
        )
        current_high = self._entry.options.get(
            CONF_HIGH_THRESHOLD,
            self._entry.data.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD),
        )
        current_sensor = self._entry.options.get(
            CONF_TEMP_SENSOR,
            self._entry.data.get(CONF_TEMP_SENSOR, DEFAULT_TEMP_SENSOR),
        )
        current_step = float(
            self._entry.options.get(
                CONF_TEMP_STEP,
                self._entry.data.get(CONF_TEMP_STEP, DEFAULT_TEMP_STEP),
            )
        )

        if user_input is not None:
            low = user_input.get(CONF_LOW_THRESHOLD, current_low)
            high = user_input.get(CONF_HIGH_THRESHOLD, current_high)
            step = user_input.get(CONF_TEMP_STEP, current_step)
            if low <= 0 or high <= 0 or low >= high:
                errors["base"] = "invalid_thresholds"
            elif step <= 0:
                errors[CONF_TEMP_STEP] = "invalid_temp_step"
            else:
                return self.async_create_entry(title="", data=user_input)

        # Build sensor selector list dynamically from entities on the system
        sensor_options = _temp_sensor_options(self.hass)
        # If previously selected sensor no longer exists, fall back gracefully
        if current_sensor not in sensor_options:
            current_sensor = DEFAULT_TEMP_SENSOR

        schema = vol.Schema(
            {
                vol.Optional(CONF_TEMP_SENSOR, default=current_sensor): vol.In(
                    sensor_options
                ),
                vol.Optional(CONF_LOW_THRESHOLD, default=current_low): vol.Coerce(
                    float
                ),
                vol.Optional(CONF_HIGH_THRESHOLD, default=current_high): vol.Coerce(
                    float
                ),
                vol.Optional(CONF_TEMP_STEP, default=current_step): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "low_desc": "Degrees C below setpoint to switch to Low Heat",
                "high_desc": "Degrees C below setpoint to switch to Full Heat (must be > Low threshold)",
            },
        )


def _test_connection(host: str) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, 2000))
        sock.close()
        return True
    except OSError:
        return False
