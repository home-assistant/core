"""Config flow for the Kii Audio integration."""

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_SYSTEM_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _decode_property(value: Any) -> str | None:
    """Decode a zeroconf TXT property."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def _supports_plain_websocket_backend(data: dict[str, Any]) -> bool:
    """Return whether discovered device advertises the plain WebSocket backend."""
    version = data.get("version")
    if isinstance(version, bool):
        return False
    if isinstance(version, int | float):
        return version > 1
    if isinstance(version, str):
        try:
            return float(version) > 1
        except ValueError:
            return False
    return False


class KiiAudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kii Audio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            system_id = user_input[CONF_SYSTEM_ID]
            await self.async_set_unique_id(system_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            return self.async_create_entry(
                title="Kii Audio",
                data={
                    CONF_HOST: host,
                    CONF_SYSTEM_ID: system_id,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_SYSTEM_ID): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Kii Audio device found via zeroconf: %s", discovery_info)

        raw_data = _decode_property(discovery_info.properties.get("data"))
        if raw_data is None:
            _LOGGER.debug(
                "Ignoring Kii Audio zeroconf discovery without data property: %s",
                discovery_info,
            )
            return self.async_abort(reason="invalid_discovery_info")

        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            _LOGGER.debug(
                "Ignoring Kii Audio zeroconf discovery with invalid data property: %s",
                raw_data,
            )
            return self.async_abort(reason="invalid_discovery_info")

        device_id = data.get("deviceId")
        system_id = data.get("systemId")
        if not isinstance(device_id, str) or not isinstance(system_id, str):
            _LOGGER.debug(
                "Ignoring Kii Audio zeroconf discovery with missing IDs: %s", data
            )
            return self.async_abort(reason="invalid_discovery_info")

        if not _supports_plain_websocket_backend(data):
            _LOGGER.debug(
                "Ignoring Kii Audio zeroconf discovery with legacy backend: %s",
                data,
            )
            return self.async_abort(reason="unsupported_backend")

        host = (
            data.get("ip") if isinstance(data.get("ip"), str) else discovery_info.host
        )
        await self.async_set_unique_id(system_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: host,
                CONF_DEVICE_ID: device_id,
                CONF_SYSTEM_ID: system_id,
            }
        )

        return self.async_create_entry(
            title="Kii Audio",
            data={
                CONF_HOST: host,
                CONF_DEVICE_ID: device_id,
                CONF_SYSTEM_ID: system_id,
            },
        )
