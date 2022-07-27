"""Config flow for Yale Access Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any, cast

from bleak_retry_connector import BleakError
import voluptuous as vol
from yalexs_ble import AuthError, PushLock, local_name_to_serial, serial_to_local_name

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_integration

from .const import CONF_KEY, CONF_LOCAL_NAME, CONF_SLOT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yale Access Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._discovered_key: str | None = None
        self._discovered_slot: int | None = None
        self._discovered_name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.name)
        self._abort_if_unique_id_configured()
        self._discovery_info = cast(BluetoothServiceInfoBleak, discovery_info)
        self.context["title_placeholders"] = {
            "name": local_name_to_serial(discovery_info.name),
            "address": discovery_info.address,
        }
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a discovered integration."""
        name = discovery_info["name"]
        serial = discovery_info["serial"]
        discovered_key = discovery_info["key"]
        discovered_slot = discovery_info["slot"]
        local_name = serial_to_local_name(serial)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.unique_id == local_name:
                updates: dict[str, str | int] = {}
                if entry.data[CONF_KEY] != discovered_key:
                    updates[CONF_KEY] = discovered_key
                    updates[CONF_SLOT] = discovered_slot
                if updates:
                    self.hass.config_entries.async_update_entry(entry, data=updates)
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                return self.async_abort(reason="already_configured")
        for ble_discovery in async_discovered_service_info(self.hass):
            if local_name == ble_discovery.name:
                self._discovery_info = ble_discovery
                break
        if not self._discovery_info:
            return self.async_abort(reason="no_devices_found")
        self._discovered_name = name
        self._discovered_key = discovered_key
        self._discovered_slot = discovered_slot
        for progress in self._async_in_progress(include_uninitialized=True):
            # Integration discovery should abort other discovery types
            # since it already has the keys and slots, and the other
            # discovery types do not.
            context = progress["context"]
            if context.get(
                "unique_id"
            ) == self._discovery_info.name and not context.get("active"):
                self.hass.config_entries.flow.async_abort(progress["flow_id"])
        await self.async_set_unique_id(self._discovery_info.name)
        self.context["title_placeholders"] = {
            "name": self._discovered_name,
            "address": self._discovery_info.address,
        }
        return await self.async_step_integration_discovery_confirm()

    async def async_step_integration_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation of discovered integration."""
        assert self._discovered_key is not None
        assert self._discovered_slot is not None
        assert self._discovery_info is not None
        assert self._discovered_name is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name,
                data={
                    CONF_KEY: self._discovered_key,
                    CONF_SLOT: self._discovered_slot,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="integration_discovery_confirm",
            description_placeholders={
                CONF_LOCAL_NAME: self._discovery_info.name,
                CONF_ADDRESS: self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.context["active"] = True
            local_name = user_input[CONF_LOCAL_NAME]
            discovery_info = self._discovered_devices[local_name]
            key = user_input[CONF_KEY]
            slot = user_input[CONF_SLOT]
            await self.async_set_unique_id(local_name, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            push_lock = PushLock(local_name)
            push_lock.set_ble_device(discovery_info.device)
            push_lock.set_lock_key(key, slot)
            try:
                await push_lock.update()
            except BleakError:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["key"] = "invalid_auth"
            except AuthError:
                errors["key"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=local_name, data=user_input)

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.name] = discovery
        else:
            current_local_names = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.name in current_local_names
                    or discovery.name in self._discovered_devices
                ):
                    continue
                self._discovered_devices[discovery.name] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LOCAL_NAME): vol.In(
                    {
                        local_name: f"{local_name} ({service_info.address})"
                        for local_name, service_info in self._discovered_devices.items()
                    }
                ),
                vol.Required(CONF_KEY): str,
                vol.Required(CONF_SLOT): int,
            }
        )
        integration = await async_get_integration(self.hass, DOMAIN)
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"docs_url": integration.documentation},
        )
