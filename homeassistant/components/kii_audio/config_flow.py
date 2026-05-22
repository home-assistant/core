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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SYSTEM_ID): str,
    }
)


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
    await client.start()
    try:
        async with asyncio.timeout(10):
            await ready.wait()
    except TimeoutError as err:
        raise CannotConnect from err
    finally:
        await client.stop()

    return system_info


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    system_info = await _async_get_system_info(hass, data[CONF_HOST])
    system_id = system_info.get("systemId")
    if isinstance(system_id, str) and system_id != data[CONF_SYSTEM_ID]:
        raise InvalidSystemId


class KiiAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kii Audio."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidSystemId:
                errors["base"] = "invalid_system_id"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_SYSTEM_ID])
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
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

        raw_data = discovery_info.properties.get("data")
        if not isinstance(raw_data, str):
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

        host = data.get("ip")
        if not isinstance(host, str) or not host:
            host = discovery_info.host
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


class InvalidSystemId(HomeAssistantError):
    """Error to indicate the provided system ID does not match."""
