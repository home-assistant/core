"""Config flow for the Spin EV Charger integration."""

import logging
import re
from typing import Any, override

from habluetooth import HaBleakClientWrapper
from spinev_ble import ADVERTISED_NAME_PATTERN, SpinEvCharger, SpinEvError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CONNECTION_MODE,
    CONF_SERIAL,
    DEFAULT_CONNECTION_MODE,
    DOMAIN,
    ConnectionMode,
)
from .coordinator import SpinEvConfigEntry

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_MODE): SelectSelector(
            SelectSelectorConfig(
                options=[mode.value for mode in ConnectionMode],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_CONNECTION_MODE,
            )
        )
    }
)


def serial_from_name(name: str | None) -> str | None:
    """Return the serial from an advertised name, or None if it is not one.

    The service UUID the charger advertises is a generic serial over BLE
    tunnel used by many unrelated devices, so the name is what actually tells
    a charger apart from them.
    """
    if name is None or not re.match(ADVERTISED_NAME_PATTERN, name):
        return None
    return name.strip().split("_")[0]


class SpinEvOptionsFlow(OptionsFlow):
    """Handle the options for a charger."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how the charger's single Bluetooth slot is used."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_CONNECTION_MODE: self.config_entry.options.get(
                        CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE
                    )
                },
            ),
        )


class SpinEvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Spin EV Charger."""

    VERSION = 1

    _address: str
    _serial: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, str] = {}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: SpinEvConfigEntry) -> SpinEvOptionsFlow:
        """Return the options flow."""
        return SpinEvOptionsFlow()

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a charger discovered over Bluetooth."""
        serial = serial_from_name(discovery_info.name)
        if serial is None:
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._address = discovery_info.address
        self._serial = serial
        self.context["title_placeholders"] = {"name": serial}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered charger."""
        if user_input is not None:
            if await self._async_charger_answers(self._address, self._serial):
                return self._async_create(self._address, self._serial)
            # There is nothing to correct on a confirm step, so a charger that
            # will not answer ends the flow rather than looping on itself.
            return self.async_abort(reason="cannot_connect")

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._serial},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a charger from the ones already seen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            serial = self._discovered[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if await self._async_charger_answers(address, serial):
                return self._async_create(address, serial)
            errors["base"] = "cannot_connect"
        else:
            # The charger only answers a connectable scan, and a passive-only
            # adapter will not have it in range yet on the first pass.
            await bluetooth.async_request_active_scan(self.hass)

            current = self._async_current_ids(include_ignore=False)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.address in current:
                    continue
                if (found := serial_from_name(info.name)) is not None:
                    self._discovered[info.address] = found

            if not self._discovered:
                return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
            errors=errors,
        )

    async def _async_charger_answers(self, address: str, serial: str) -> bool:
        """Return True if the charger is in range and replies to a read."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            return False

        charger = SpinEvCharger(
            ble_device, client_class=HaBleakClientWrapper, max_attempts=1
        )
        try:
            async with charger:
                await charger.async_get_state_value()
        except SpinEvError as err:
            _LOGGER.debug("Could not reach charger %s: %s", serial, err)
            return False
        return True

    @callback
    def _async_create(self, address: str, serial: str) -> ConfigFlowResult:
        """Store the charger."""
        return self.async_create_entry(
            title=serial,
            data={CONF_ADDRESS: address, CONF_SERIAL: serial},
            options={CONF_CONNECTION_MODE: DEFAULT_CONNECTION_MODE},
        )
