"""Config flows for Senziio integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_MODEL, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .device import SenziioDevice
from .entity import DOMAIN, MANUFACTURER
from .exceptions import CannotConnect, MQTTNotEnabled, RepeatedTitle

_LOGGER = logging.getLogger(__name__)

_input_type = vol.All(str, vol.Strip)


class SenziioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flows for Senziio Sensor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle Senziio user setup."""
        errors: dict[str, str] = {}

        device_id = ""
        device_model = ""
        friendly_name = self._get_friendly_name()

        if user_input is not None:
            device_id = user_input[CONF_UNIQUE_ID]
            device_model = user_input[CONF_MODEL]
            friendly_name = user_input[CONF_FRIENDLY_NAME]

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            try:
                data = await validate_input(self.hass, user_input)
            except MQTTNotEnabled:
                errors["base"] = "mqtt_not_enabled"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except RepeatedTitle:
                errors["base"] = "repeated_title"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=friendly_name,
                    data=data,
                )

        step_user_data_schema = vol.Schema(
            {
                vol.Required(CONF_UNIQUE_ID, default=device_id): _input_type,
                vol.Required(CONF_MODEL, default=device_model): _input_type,
                vol.Required(CONF_FRIENDLY_NAME, default=friendly_name): _input_type,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=step_user_data_schema, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle Senziio device discovered via Zeroconf."""
        _LOGGER.info("Discovered Senziio device via Zeroconf")

        device_id = discovery_info.properties["device_id"]

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        self.context[CONF_UNIQUE_ID] = device_id
        self.context[CONF_MODEL] = discovery_info.properties["device_model"]

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm the addition of a Senziio device discovered via Zeroconf."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = self.context[CONF_UNIQUE_ID]
            friendly_name = user_input[CONF_FRIENDLY_NAME]
            data_input = {
                CONF_UNIQUE_ID: device_id,
                CONF_MODEL: self.context[CONF_MODEL],
                CONF_FRIENDLY_NAME: friendly_name,
            }

            try:
                data = await validate_input(self.hass, data_input)
            except MQTTNotEnabled:
                errors["base"] = "mqtt_not_enabled"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except RepeatedTitle:
                errors["base"] = "repeated_title"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=friendly_name,
                    data=data,
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_FRIENDLY_NAME,
                    default=self._get_friendly_name(),
                ): vol.All(str, vol.Strip),
            }
        )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "device_id": self.context[CONF_UNIQUE_ID],
                "device_model": self.context[CONF_MODEL],
            },
            data_schema=data_schema,
            errors=errors,
        )

    def _get_friendly_name(self):
        """Get a unique friendly name to display as device title."""
        used_titles = {
            entry.title for entry in self._async_current_entries(include_ignore=True)
        }
        prefix = MANUFACTURER
        if model := self.context.get(CONF_MODEL):
            prefix = f"{MANUFACTURER} {model}"
        number = len(used_titles) + 1
        while (title := f"{prefix} {number}") in used_titles:
            number += 1
        return title


async def validate_input(
    hass: HomeAssistant, data_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate input data."""
    # check friendly name is unique
    friendly_name = _sanitize(data_input[CONF_FRIENDLY_NAME])
    existing_titles = {
        entry.title for entry in hass.config_entries.async_entries(DOMAIN)
    }
    if friendly_name in existing_titles:
        raise RepeatedTitle

    # validate device response
    device_id = _sanitize(data_input[CONF_UNIQUE_ID])
    device_model = _sanitize(data_input[CONF_MODEL])
    device = SenziioDevice(device_id, device_model, hass)
    device_info = await device.get_info()

    if not device_info:
        raise CannotConnect

    return {
        CONF_UNIQUE_ID: device_id,
        CONF_MODEL: device_model,
        CONF_FRIENDLY_NAME: friendly_name,
        **device_info,
    }


def _sanitize(value: str) -> str:
    """Sanitize entry value."""
    return " ".join(value.split())
