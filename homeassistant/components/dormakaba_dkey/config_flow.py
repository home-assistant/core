"""Config flow for Dormakaba dKey integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from bleak import BleakError
from py_dormakaba_dkey import DKEYLock, device_filter, errors as dkey_errors
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_last_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_ASSOCIATION_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_ASSOCIATE_SCHEMA = vol.Schema(
    {
        vol.Required("activation_code"): str,
    }
)


class DormkabaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dormakaba dKey."""

    VERSION = 1

    _reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._lock: DKEYLock | None = None
        # Populated by user step
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        # Populated by bluetooth, reauth_confirm and user steps
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            # Guard against the user selecting a device which has been configured by
            # another flow.
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[address]
            return await self.async_step_associate()

        current_addresses = self._async_current_ids()
        for discovery in async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or not device_filter(discovery.advertisement)
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
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        name = self._discovery_info.name or self._discovery_info.address
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle bluetooth confirm step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        if user_input is None:
            name = self._discovery_info.name or self._discovery_info.address
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders={"name": name},
            )

        return await self.async_step_associate()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}
        reauth_entry = self._reauth_entry
        assert reauth_entry is not None

        if user_input is not None:
            if (
                discovery_info := async_last_service_info(
                    self.hass, reauth_entry.data[CONF_ADDRESS], True
                )
            ) is None:
                errors = {"base": "no_longer_in_range"}
            else:
                self._discovery_info = discovery_info
                return await self.async_step_associate()

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_associate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle associate step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        if user_input is None:
            return self.async_show_form(
                step_id="associate", data_schema=STEP_ASSOCIATE_SCHEMA
            )

        errors = {}
        if not self._lock:
            self._lock = DKEYLock(self._discovery_info.device)
        lock = self._lock

        try:
            association_data = await lock.associate(user_input["activation_code"])
        except BleakError as err:
            _LOGGER.warning("BleakError", exc_info=err)
            return self.async_abort(reason="cannot_connect")
        except dkey_errors.InvalidActivationCode:
            errors["base"] = "invalid_code"
        except dkey_errors.WrongActivationCode:
            errors["base"] = "wrong_code"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            data = {
                CONF_ADDRESS: self._discovery_info.device.address,
                CONF_ASSOCIATION_DATA: association_data.to_json(),
            }
            if reauth_entry := self._reauth_entry:
                self.hass.config_entries.async_update_entry(reauth_entry, data=data)
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(
                title=lock.device_info.device_name
                or lock.device_info.device_id
                or lock.name,
                data=data,
            )

        return self.async_show_form(
            step_id="associate", data_schema=STEP_ASSOCIATE_SCHEMA, errors=errors
        )
