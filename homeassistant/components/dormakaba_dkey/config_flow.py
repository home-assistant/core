"""Config flow for Dormakaba dKey integration."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakError
from py_dormakaba_dkey import DKEYLock, errors as dkey_errors
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_rediscover_address,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ASSOCIATION_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_ASSOCIATE_SCHEMA = vol.Schema(
    {
        vol.Required("activation_code"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dormakaba dKey."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._lock: DKEYLock | None = None
        # Populated by user step
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        # Populated by bluetooth and user steps
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step.

        The user will be shown a list of matching discovery flows automatically,
        so we just abort a user flow.
        """
        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="no_additional_devices_found")
        return self.async_abort(reason="no_devices_found")

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        name = self._discovery_info.name or self._discovery_info.address
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    async def async_step_associate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
        except BleakError:
            return self.async_abort(reason="cannot_connect")
        except dkey_errors.InvalidActivationCode:
            errors["base"] = "invalid_code"
        except dkey_errors.WrongActivationCode:
            errors["base"] = "wrong_code"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            return self.async_create_entry(
                title=lock.device_info.device_name
                or lock.device_info.device_id
                or lock.name,
                data={
                    CONF_ADDRESS: self._discovery_info.device.address,
                    CONF_ASSOCIATION_DATA: association_data.to_json(),
                },
            )

        return self.async_show_form(
            step_id="associate", data_schema=STEP_ASSOCIATE_SCHEMA, errors=errors
        )

    async def async_step_unignore(self, user_input: dict[str, Any]) -> FlowResult:
        """Unignore an ignored bluetooth discovery flow."""
        async_rediscover_address(self.hass, user_input["unique_id"])
        return self.async_abort(reason="already_in_progress")
