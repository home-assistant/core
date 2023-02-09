"""Config flow for Dormakaba dKey integration."""
from __future__ import annotations

from asyncio import Task
import logging
from typing import Any

from bleak import BleakError
from py_dormakaba_dkey import DKEYLock, device_filter, errors as dkey_errors
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
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
    _lock: DKEYLock

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connect_task: Task | None = None
        # Populated by user step
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        # Populated by bluetooth and user steps
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[address]
            return await self.async_step_bluetooth_connect()

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

        return await self.async_step_bluetooth_connect()

    async def async_step_bluetooth_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle bluetooth confirm step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        async def _connect() -> None:
            try:
                await self._lock.connect()
                # Disconnect again so the user can use the admin app to create a new key
                await self._lock.disconnect()
            finally:
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
                )

        if not self._connect_task:
            self._lock = DKEYLock(self._discovery_info.device)
            self._connect_task = self.hass.async_create_task(_connect())
            return self.async_show_progress(
                step_id="bluetooth_connect",
                progress_action="wait_for_bluetooth_connect",
            )

        try:
            await self._connect_task
        except BleakError as err:
            _LOGGER.info("Could not connect to lock", exc_info=err)
            return self.async_show_progress_done(next_step_id="could_not_connect")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unknown error when connecting to lock", exc_info=err)
            return self.async_show_progress_done(next_step_id="could_not_connect")
        finally:
            self._connect_task = None

        return self.async_show_progress_done(next_step_id="associate")

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
        lock = self._lock

        try:
            association_data = await lock.associate(user_input["activation_code"])
        except dkey_errors.InvalidActivationCode:
            errors["base"] = "invalid_code"
        except dkey_errors.WrongActivationCode:
            errors["base"] = "wrong_code"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
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

    async def async_step_could_not_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle connection failure."""
        if user_input is None:
            return self.async_show_form(step_id="could_not_connect")

        return await self.async_step_bluetooth_connect()
