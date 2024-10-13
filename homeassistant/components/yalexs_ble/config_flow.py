"""Config flow for Yale Access Bluetooth integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Self

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

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_ALWAYS_CONNECTED, CONF_KEY, CONF_LOCAL_NAME, CONF_SLOT, DOMAIN
from .util import async_find_existing_service_info, human_readable_name

_LOGGER = logging.getLogger(__name__)


async def async_validate_lock_or_error(
    local_name: str, device: BLEDevice, key: str, slot: int
) -> dict[str, str]:
    """Validate the lock and return errors if any."""
    if len(key) != 32:
        return {CONF_KEY: "invalid_key_format"}
    try:
        bytes.fromhex(key)
    except ValueError:
        return {CONF_KEY: "invalid_key_format"}
    if not isinstance(slot, int) or not 0 <= slot <= 255:
        return {CONF_SLOT: "invalid_key_index"}
    try:
        await PushLock(local_name, device.address, device, key, slot).validate()
    except (DisconnectedError, AuthError, ValueError):
        return {CONF_KEY: "invalid_auth"}
    except BleakError:
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected error")
        return {"base": "unknown"}
    return {}


class YalexsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yale Access Bluetooth."""

    VERSION = 1

    _address: str | None = None
    _local_name_is_unique = False
    active = False
    local_name: str | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._lock_cfg: ValidatedLockConfig | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self.local_name = discovery_info.name
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            ),
        }
        return await self.async_step_user()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle a discovered integration."""
        lock_cfg = ValidatedLockConfig(
            discovery_info["name"],
            discovery_info["address"],
            discovery_info["serial"],
            discovery_info["key"],
            discovery_info["slot"],
        )

        address = lock_cfg.address
        self.local_name = lock_cfg.local_name
        self._local_name_is_unique = local_name_is_unique(self.local_name)

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
                self._local_name_is_unique
                and entry.data.get(CONF_LOCAL_NAME) == lock_cfg.local_name
            ):
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **new_data}, reason="already_configured"
                )

        self._discovery_info = async_find_existing_service_info(
            self.hass, self.local_name, address
        )
        if not self._discovery_info:
            return self.async_abort(reason="no_devices_found")

        self._address = address
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            raise AbortFlow("already_in_progress")

        self._lock_cfg = lock_cfg
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                lock_cfg.name, lock_cfg.local_name, self._discovery_info.address
            )
        }
        return await self.async_step_integration_discovery_confirm()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        # Integration discovery should abort other flows unless they
        # are already in the process of being set up since this discovery
        # will already have all the keys and the user can simply confirm.
        if (
            self._local_name_is_unique and other_flow.local_name == self.local_name
        ) or other_flow.unique_id == self._address:
            if other_flow.active:
                # The user has already started interacting with this flow
                # and entered the keys. We abort the discovery flow since
                # we assume they do not want to use the discovered keys for
                # some reason.
                return True
            self.hass.config_entries.flow.async_abort(other_flow.flow_id)

        return False

    async def async_step_integration_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_validate()

    async def async_step_reauth_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth and validation."""
        errors = {}
        reauth_entry = self._reauth_entry
        assert reauth_entry is not None
        if user_input is not None:
            if (
                device := async_ble_device_from_address(
                    self.hass, reauth_entry.data[CONF_ADDRESS], True
                )
            ) is None:
                errors = {"base": "no_longer_in_range"}
            elif not (
                errors := await async_validate_lock_or_error(
                    reauth_entry.data[CONF_LOCAL_NAME],
                    device,
                    user_input[CONF_KEY],
                    user_input[CONF_SLOT],
                )
            ):
                return self.async_update_reload_and_abort(
                    reauth_entry, data={**reauth_entry.data, **user_input}
                )

        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema(
                {vol.Required(CONF_KEY): str, vol.Required(CONF_SLOT): int}
            ),
            description_placeholders={
                "address": reauth_entry.data[CONF_ADDRESS],
                "title": reauth_entry.title,
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.active = True
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            local_name = discovery_info.name
            key = user_input[CONF_KEY]
            slot = user_input[CONF_SLOT]
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            if not (
                errors := await async_validate_lock_or_error(
                    local_name, discovery_info.device, key, slot
                )
            ):
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
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> YaleXSBLEOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YaleXSBLEOptionsFlowHandler(config_entry)


class YaleXSBLEOptionsFlowHandler(OptionsFlow):
    """Handle YaleXSBLE options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize YaleXSBLE options flow."""
        self.entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the YaleXSBLE options."""
        return await self.async_step_device_options()

    async def async_step_device_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the YaleXSBLE devices options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_ALWAYS_CONNECTED: user_input[CONF_ALWAYS_CONNECTED]},
            )

        return self.async_show_form(
            step_id="device_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALWAYS_CONNECTED,
                        default=self.entry.options.get(CONF_ALWAYS_CONNECTED, False),
                    ): bool,
                }
            ),
        )
