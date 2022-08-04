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
    local_name_to_serial,
)
from yalexs_ble.const import YALE_MFR_ID

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.components.bluetooth.match import (
    LOCAL_NAME,
    BluetoothCallbackMatcher,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_integration

from .const import CONF_KEY, CONF_LOCAL_NAME, CONF_SLOT, DISCOVERY_TIMEOUT, DOMAIN

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
    await PushLock(local_name, device, key, slot).validate()


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
        await self.async_set_unique_id(discovery_info.name)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": local_name_to_serial(discovery_info.name),
            "local_name": discovery_info.name,
            "address": self._discovery_info.address,
        }
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a discovered integration."""
        lock_cfg = ValidatedLockConfig(
            discovery_info["name"],
            discovery_info["serial"],
            discovery_info["key"],
            discovery_info["slot"],
        )
        # We do not want to raise on progress as integration_discovery takes
        # precedence over other discovery flows since we already have the keys.
        await self.async_set_unique_id(lock_cfg.local_name, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={CONF_KEY: lock_cfg.key, CONF_SLOT: lock_cfg.slot}
        )
        for progress in self._async_in_progress(include_uninitialized=True):
            # Integration discovery should abort other discovery types
            # since it already has the keys and slots, and the other
            # discovery types do not.
            context = progress["context"]
            if context.get("unique_id") == lock_cfg.local_name and not context.get(
                "active"
            ):
                self.hass.config_entries.flow.async_abort(progress["flow_id"])

        try:
            self._discovery_info = await bluetooth.async_process_advertisements(
                self.hass,
                lambda service_info: True,
                BluetoothCallbackMatcher({LOCAL_NAME: lock_cfg.local_name}),
                bluetooth.BluetoothScanningMode.ACTIVE,
                DISCOVERY_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return self.async_abort(reason="no_devices_found")
        self._lock_cfg = lock_cfg
        self.context["title_placeholders"] = {
            "name": lock_cfg.name,
            "local_name": lock_cfg.local_name,
            "address": self._discovery_info.address,
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
                    CONF_KEY: self._lock_cfg.key,
                    CONF_SLOT: self._lock_cfg.slot,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="integration_discovery_confirm",
            description_placeholders={
                "name": self._lock_cfg.name,
                "local_name": self.unique_id,
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
            local_name = user_input[CONF_LOCAL_NAME]
            discovery_info = self._discovered_devices[local_name]
            key = user_input[CONF_KEY]
            slot = user_input[CONF_SLOT]
            await self.async_set_unique_id(local_name, raise_on_progress=False)
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
                        CONF_KEY: key,
                        CONF_SLOT: slot,
                    },
                )

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.name] = discovery
        else:
            current_local_names = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.name in current_local_names
                    or discovery.name in self._discovered_devices
                    or YALE_MFR_ID not in discovery.manufacturer_data
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


class InvalidKeyFormat(HomeAssistantError):
    """Invalid key format."""


class InvalidKeyIndex(HomeAssistantError):
    """Invalid key index."""
