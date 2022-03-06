"""Config flow for KDEConnect integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from cryptography.hazmat.primitives import serialization
from pykdeconnect.client import KdeConnectClient
from pykdeconnect.const import PairingResult
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_DEVICE_CERT,
    CONF_DEVICE_INCOMING_CAPS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OUTGOING_CAPS,
    CONF_DEVICE_TYPE,
    CONF_REFRESH,
    CONNECT_TIMEOUT,
    DATA_KEY_CLIENT,
    DATA_KEY_NAMES,
    DOMAIN,
)
from .helpers import ensure_running

_LOGGER = logging.getLogger(__name__)


async def try_pair(hass: HomeAssistant, device_id: str) -> dict[str, Any]:
    """Try pairing to the selected device."""

    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])

    device = client.connected_devices[device_id]
    result = await device.pair()
    if result == PairingResult.REJECTED:
        raise PairingRejected()

    if result == PairingResult.TIMEOUT:
        raise PairingTimeout()

    if result == PairingResult.ACCEPTED:
        cert = device.certificate
        assert cert is not None

        return {
            CONF_DEVICE_NAME: device.device_name,
            CONF_DEVICE_ID: device_id,
            CONF_DEVICE_TYPE: device.device_type.value,
            CONF_DEVICE_CERT: cert.public_bytes(serialization.Encoding.PEM).decode(
                "utf-8"
            ),
            CONF_DEVICE_INCOMING_CAPS: list(device.incoming_capabilities),
            CONF_DEVICE_OUTGOING_CAPS: list(device.outgoing_capabilities),
        }

    assert False  # pragma: no cover


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KDEConnect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await ensure_running(self.hass)

        client = cast(KdeConnectClient, self.hass.data[DOMAIN][DATA_KEY_CLIENT])

        if user_input is None:
            return self.async_show_device_selection(client)

        if user_input[CONF_DEVICE_NAME] == CONF_REFRESH:
            await client.advertise_once()
            # Allow some time for devices to respond to our request
            await asyncio.sleep(CONNECT_TIMEOUT)
            return self.async_show_device_selection(client)

        device_id = self.hass.data[DOMAIN][DATA_KEY_NAMES][user_input[CONF_DEVICE_NAME]]

        return await self.async_step_pair(device_id)

    async def async_step_pair(self, device_id: str) -> FlowResult:
        """Handle the pairing after selecting a device."""
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        client = self.hass.data[DOMAIN][DATA_KEY_CLIENT]

        errors = {}
        try:
            data = await try_pair(self.hass, device_id)
        except PairingRejected:
            errors["base"] = "rejected"
        except PairingTimeout:
            errors["base"] = "timeout"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=data[CONF_DEVICE_NAME], data=data)

        return self.async_show_device_selection(client, errors=errors)

    def async_show_device_selection(
        self, client: KdeConnectClient, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show a device selection dialog."""
        devices = client.pairable_devices
        device_names_to_id = {}
        if self.show_advanced_options:
            device_names_to_id = {
                f"{d.device_name} ({d.device_id})": d.device_id for d in devices
            }
        else:
            for device in devices:
                if (
                    device.device_name not in device_names_to_id
                    and device.device_name != CONF_REFRESH
                ):
                    device_name = device.device_name
                else:
                    count = 1
                    device_name = f"{device.device_name} ({count})"
                    while device_name in device_names_to_id:
                        count += 1
                        device_name = f"{device.device_name} ({count})"
                device_names_to_id[device_name] = device.device_id

        self.hass.data[DOMAIN][DATA_KEY_NAMES] = device_names_to_id
        devices_names = sorted(device_names_to_id.keys())
        devices_names.append(CONF_REFRESH)

        schema = vol.Schema({vol.Required(CONF_DEVICE_NAME): vol.In(devices_names)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class PairingRejected(HomeAssistantError):
    """Error to indicate that the pairing request was rejected."""


class PairingTimeout(HomeAssistantError):
    """Error to indicate that the pairing request timed out."""
