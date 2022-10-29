"""Config flow for Yale Access Bluetooth integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak_retry_connector import BleakError, BLEDevice
import voluptuous as vol
from yalexs_ble import (
    AuthError,
    DisconnectedError,
    PushLock,
    ValidatedLockConfig,
    local_name_is_unique,
)
from yalexs_ble.const import YALE_MFR_ID

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_KEY, CONF_LOCAL_NAME, CONF_SLOT, DOMAIN
from .util import async_get_service_info, human_readable_name

_LOGGER = logging.getLogger(__name__)


async def validate_lock(
    local_name: str, device: BLEDevice, key: str, slot: int
) -> None:
    """Validate a lock."""
    if len(key) != 32:
        raise InvalidKeyFormat
    try:
        bytes.fromhex(key)
    except ValueError as ex:
        raise InvalidKeyFormat from ex
    if not isinstance(slot, int) or slot < 0 or slot > 255:
        raise InvalidKeyIndex
    await PushLock(local_name, device.address, device, key, slot).validate()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yale Access Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._lock_cfg: ValidatedLockConfig | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self.context["local_name"] = discovery_info.name
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            ),
        }
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a discovered integration."""
        lock_cfg = ValidatedLockConfig(
            discovery_info["name"],
            discovery_info["address"],
            discovery_info["serial"],
            discovery_info["key"],
            discovery_info["slot"],
        )

        address = lock_cfg.address
        local_name = lock_cfg.local_name
        hass = self.hass

        # We do not want to raise on progress as integration_discovery takes
        # precedence over other discovery flows since we already have the keys.
        #
        # After we do discovery we will abort the flows that do not have the keys
        # below unless the user is already setting them up.
        await self.async_set_unique_id(address, raise_on_progress=False)
        new_data = {CONF_KEY: lock_cfg.key, CONF_SLOT: lock_cfg.slot}
        self._abort_if_unique_id_configured(updates=new_data)
        for entry in self._async_current_entries():
            if (
                local_name_is_unique(lock_cfg.local_name)
                and entry.data.get(CONF_LOCAL_NAME) == lock_cfg.local_name
            ):
                if hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **new_data}
                ):
                    hass.async_create_task(
                        hass.config_entries.async_reload(entry.entry_id)
                    )
                raise AbortFlow(reason="already_configured")

        try:
            self._discovery_info = await async_get_service_info(
                hass, local_name, address
            )
        except asyncio.TimeoutError:
            return self.async_abort(reason="no_devices_found")

        # Integration discovery should abort other flows unless they
        # are already in the process of being set up since this discovery
        # will already have all the keys and the user can simply confirm.
        for progress in self._async_in_progress(include_uninitialized=True):
            context = progress["context"]
            if (
                local_name_is_unique(local_name)
                and context.get("local_name") == local_name
            ) or context.get("unique_id") == address:
                if context.get("active"):
                    # The user has already started interacting with this flow
                    # and entered the keys. We abort the discovery flow since
                    # we assume they do not want to use the discovered keys for
                    # some reason.
                    raise data_entry_flow.AbortFlow("already_in_progress")
                hass.config_entries.flow.async_abort(progress["flow_id"])

        self._lock_cfg = lock_cfg
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                lock_cfg.name, lock_cfg.local_name, self._discovery_info.address
            )
        }
        return await self.async_step_integration_discovery_confirm()

    async def async_step_integration_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation of discovered integration."""
        assert self._discovery_info is not None
        assert self._lock_cfg is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._lock_cfg.name,
                data={
                    CONF_LOCAL_NAME: self._discovery_info.name,
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_KEY: self._lock_cfg.key,
                    CONF_SLOT: self._lock_cfg.slot,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="integration_discovery_confirm",
            description_placeholders={
                "name": self._lock_cfg.name,
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.context["active"] = True
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            local_name = discovery_info.name
            key = user_input[CONF_KEY]
            slot = user_input[CONF_SLOT]
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            try:
                await validate_lock(local_name, discovery_info.device, key, slot)
            except InvalidKeyFormat:
                errors[CONF_KEY] = "invalid_key_format"
            except InvalidKeyIndex:
                errors[CONF_SLOT] = "invalid_key_index"
            except (DisconnectedError, AuthError, ValueError):
                errors[CONF_KEY] = "invalid_auth"
            except BleakError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=local_name,
                    data={
                        CONF_LOCAL_NAME: discovery_info.name,
                        CONF_ADDRESS: discovery_info.address,
                        CONF_KEY: key,
                        CONF_SLOT: slot,
                    },
                )

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            current_unique_names = {
                entry.data.get(CONF_LOCAL_NAME)
                for entry in self._async_current_entries()
                if local_name_is_unique(entry.data.get(CONF_LOCAL_NAME))
            }
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.name in current_unique_names
                    or discovery.address in self._discovered_devices
                    or YALE_MFR_ID not in discovery.manufacturer_data
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: f"{service_info.name} ({service_info.address})"
                        for service_info in self._discovered_devices.values()
                    }
                ),
                vol.Required(CONF_KEY): str,
                vol.Required(CONF_SLOT): int,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class InvalidKeyFormat(HomeAssistantError):
    """Invalid key format."""


class InvalidKeyIndex(HomeAssistantError):
    """Invalid key index."""
