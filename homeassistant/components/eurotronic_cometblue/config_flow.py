"""Config flow for CometBlue."""

from __future__ import annotations

import logging
from typing import Any

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue
from eurotronic_cometblue_ha.const import SERVICE
from habluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _try_connect(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Verify connection to the device with the provided PIN and read initial data."""
        device_address = self._discovery_info.address if self._discovery_info else ""
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
                except TimeoutError:
                    # This likely means PIN was incorrect on Linux and ESPHome backends
                    LOGGER.debug(
                        "Failed to read battery level, likely due to incorrect PIN",
                        exc_info=True,
                    )
                    return {"base": "invalid_pin"}
        except TimeoutError:
            LOGGER.debug("Connection to device timed out", exc_info=True)
            return {"base": "timeout_connect"}
        except BleakError:
            LOGGER.debug("Failed to connect to device", exc_info=True)
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.debug("Unknown error", exc_info=True)
            return {"base": "unknown"}
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

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=DATA_SCHEMA,
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

        current_addresses = self._async_current_ids()
        self._discovered_devices = {
            discovery_info.address: discovery_info
            for discovery_info in async_discovered_service_info(
                self.hass, connectable=True
            )
            if SERVICE in discovery_info.service_uuids
            and discovery_info.address not in current_addresses
        }

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(format_mac(address))
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices.get(address)
            return await self.async_step_bluetooth_confirm()
        # Check if there is at least one device
        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(list(self._discovered_devices))}
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        return await self.async_step_pick_device()
