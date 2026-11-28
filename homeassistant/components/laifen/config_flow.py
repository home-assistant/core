"""Config flow for the Laifen integration."""

from typing import TYPE_CHECKING, Any, override

from laifen_ble import (
    LaifenConnectionError,
    LaifenToothbrush,
    UnsupportedStateError,
    is_supported,
)
import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import AbortFlow

from .const import DOMAIN


class LaifenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laifen."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_can_connect(self, address: str) -> bool:
        """Return whether the toothbrush can be connected to."""
        ble_device = async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            return False
        toothbrush = LaifenToothbrush(ble_device)
        try:
            await toothbrush.connect()
        except UnsupportedStateError as err:
            raise AbortFlow("unsupported_firmware") from err
        except LaifenConnectionError:
            return False
        await toothbrush.disconnect()
        return True

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a discovered toothbrush."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered toothbrush."""
        discovery_info = self._discovery_info
        if TYPE_CHECKING:
            assert discovery_info is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self._async_can_connect(discovery_info.address):
                return self.async_create_entry(
                    title=discovery_info.name,
                    data={CONF_ADDRESS: discovery_info.address},
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": discovery_info.name},
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered toothbrush."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if await self._async_can_connect(address):
                return self.async_create_entry(
                    title=self._discovered_devices[address].name,
                    data={CONF_ADDRESS: address},
                )
            errors["base"] = "cannot_connect"

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if (
                address in current_addresses
                or address in self._discovered_devices
                or not is_supported(discovery_info.name)
            ):
                continue
            self._discovered_devices[address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            address: f"{discovery_info.name} ({address})"
                            for address, discovery_info in self._discovered_devices.items()
                        }
                    )
                }
            ),
            errors=errors,
        )
