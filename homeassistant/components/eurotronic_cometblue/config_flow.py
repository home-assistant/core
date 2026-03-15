"""Config flow for CometBlue."""

from __future__ import annotations

import logging
from typing import Any

from eurotronic_cometblue_ha import AsyncCometBlue
from eurotronic_cometblue_ha.const import SERVICE
from habluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PIN, default="000000"): vol.All(
            TextSelector(TextSelectorConfig(type=TextSelectorType.NUMBER)),
            vol.Length(min=6, max=6),
        ),
    }
)


def name_from_discovery(discovery: BluetoothServiceInfoBleak | None) -> str:
    """Get the name from a discovery."""
    if discovery is None:
        return "Comet Blue"
    if discovery.name == str(discovery.address):
        return discovery.address
    return f"{discovery.name} {discovery.address}"


class CometBlueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CometBlue."""

    VERSION = 1

    _existing_entry_data: dict[str, Any] = {}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_addresses: list[str] = []

    async def _try_connect(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Verify connection to the device with the provided PIN and read initial data."""
        device_address = (
            self._discovery_info.address
            if self._discovery_info
            else self._existing_entry_data[CONF_ADDRESS]
        )
        try:
            ble_device = async_ble_device_from_address(self.hass, device_address)
            LOGGER.info("Testing connection for device at address %s", device_address)
            if not ble_device:
                return {"base": "cannot_connect"}

            cometblue_device = AsyncCometBlue(
                device=ble_device,
                pin=int(user_input[CONF_PIN]),
            )

            async with cometblue_device:
                try:
                    # Device only returns battery level if PIN is correct
                    await cometblue_device.get_battery_async()
                except Exception:
                    # need to use broad exception as different exceptions are raised
                    # based on the underlying OS and backend
                    LOGGER.exception(
                        "Failed to read battery level, likely due to incorrect PIN"
                    )
                    return {"base": "invalid_pin"}
        except TimeoutError:
            LOGGER.exception("Connection to device timed out")
            return {"base": "timeout_connect"}
        except Exception:
            # need to use broad exception as different exceptions are raised
            # based on the underlying OS and backend
            LOGGER.exception("Failed to connect to device")
            return {"base": "cannot_connect"}
        return {}

    def _create_entry(
        self,
        pin: str,
    ) -> ConfigFlowResult:
        """Create an entry for a discovered device."""

        entry_data = {
            CONF_ADDRESS: self._discovery_info.address
            if self._discovery_info
            else None,
            CONF_PIN: pin,
        }

        if self.source == SOURCE_RECONFIGURE:
            entry_data[CONF_ADDRESS] = self._existing_entry_data[CONF_ADDRESS]
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data=entry_data,
            )

        return self.async_create_entry(
            title=name_from_discovery(self._discovery_info), data=entry_data
        )

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered device."""

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._try_connect(user_input)
            if not errors:
                return self._create_entry(user_input[CONF_PIN])

        schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA,
            self._existing_entry_data,
        )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=schema,
            description_placeholders={
                "name": name_from_discovery(self._discovery_info)
            },
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        address = discovery_info.address

        await self.async_set_unique_id(format_mac(address))
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

        self._discovery_info = discovery_info

        self.context["title_placeholders"] = {
            "name": name_from_discovery(self._discovery_info)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""

        discovered_devices = [
            d
            for d in async_discovered_service_info(self.hass, connectable=True)
            if SERVICE in d.service_uuids
        ]

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(format_mac(address))
            self._abort_if_unique_id_configured()

            self._discovery_info = next(
                (d for d in discovered_devices if d.address == address), None
            )
            return await self.async_step_bluetooth_confirm()

        current_addresses = self._async_current_ids()
        for discovery_info in discovered_devices:
            address = discovery_info.address
            if (
                address not in current_addresses
                and address not in self._discovered_addresses
            ):
                self._discovered_addresses.append(address)

        addresses = {
            address
            for address in self._discovered_addresses
            if address not in current_addresses
        }

        # Check if there is at least one device
        if not addresses:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(addresses)}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        return await self.async_step_pick_device()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        self._existing_entry_data = dict(self._get_reconfigure_entry().data)
        return await self.async_step_bluetooth_confirm()
