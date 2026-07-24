"""Config flow for the Kii Audio integration."""

import asyncio
import json
import logging
from typing import Any

from aiokii import KiiAudioClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_SYSTEM_ID, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

LEGACY_SOCKET_IO_BACKEND_VERSION = 1

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SYSTEM_ID): str,
    }
)


async def _async_get_system_info(hass: HomeAssistant, host: str) -> dict[str, Any]:
    """Fetch system information from a Kii Audio system."""
    system_info: dict[str, Any] = {}
    ready = asyncio.Event()
    client = KiiAudioClient(async_get_clientsession(hass), host)

    def _handle_event(event: str, payload: dict[str, Any]) -> None:
        """Handle validation client events."""
        if event == "pushSystemInfo":
            system_info.update(payload)
            ready.set()

    client.add_listener(_handle_event)
    try:
        await client.start()
        async with asyncio.timeout(10):
            await ready.wait()
    except TimeoutError as err:
        raise CannotConnect from err
    finally:
        await client.stop()

    return system_info


class KiiAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kii Audio."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                system_info = await _async_get_system_info(
                    self.hass, user_input[CONF_HOST]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if system_info.get("systemId") != user_input[CONF_SYSTEM_ID]:
                    errors["base"] = "invalid_system_id"
                else:
                    await self.async_set_unique_id(user_input[CONF_SYSTEM_ID])
                    self._abort_if_unique_id_configured(updates=user_input)
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Kii Audio device found via zeroconf: %s", discovery_info)

        try:
            data = json.loads(discovery_info.properties["data"])
            device_id = data["deviceId"]
            system_id = data["systemId"]
            backend_version = data.get("version", LEGACY_SOCKET_IO_BACKEND_VERSION)
        except KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError:
            _LOGGER.debug(
                "Ignoring Kii Audio zeroconf discovery with invalid data property: %s",
                discovery_info.properties.get("data"),
            )
            return self.async_abort(reason="invalid_discovery_info")

        if not system_id:
            _LOGGER.debug(
                "Ignoring Kii Audio discovery for device without a system ID: %s",
                device_id,
            )
            return self.async_abort(reason="invalid_discovery_info")

        try:
            if backend_version <= LEGACY_SOCKET_IO_BACKEND_VERSION:
                _LOGGER.debug(
                    "Ignoring Kii Audio discovery with legacy backend version: %s",
                    backend_version,
                )
                return self.async_abort(reason="unsupported_backend")
        except TypeError:
            _LOGGER.debug(
                "Ignoring Kii Audio discovery with invalid backend version: %s",
                backend_version,
            )
            return self.async_abort(reason="invalid_discovery_info")

        host = data.get("ip") or discovery_info.host
        await self.async_set_unique_id(system_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: host,
                CONF_DEVICE_ID: device_id,
                CONF_SYSTEM_ID: system_id,
            }
        )

        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={
                CONF_HOST: host,
                CONF_DEVICE_ID: device_id,
                CONF_SYSTEM_ID: system_id,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
