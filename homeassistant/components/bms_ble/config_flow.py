"""Config flow for BLE Battery Management System integration."""

from dataclasses import dataclass
from typing import Any, Final

from aiobmsble.utils import bms_identify
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, LOGGER


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Battery Management System."""

    VERSION = 2
    MINOR_VERSION = 0

    @dataclass
    class DiscoveredDevice:
        """A discovered Bluetooth device."""

        name: str
        discovery_info: BluetoothServiceInfoBleak
        type: str

        def model(self) -> str:
            """Return BMS type in capital letters, e.g. 'DUMMY BMS'."""
            return self.type.rsplit(".", 1)[-1].replace("_", " ").upper()

    def __init__(self) -> None:
        """Initialize the config flow."""

        self._disc_dev: ConfigFlow.DiscoveredDevice | None = None
        self._disc_devs: dict[str, ConfigFlow.DiscoveredDevice] = {}

    async def _async_device_supported(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> str | None:
        """Check if device is supported by an available BMS class."""
        if not (
            bms_class := await bms_identify(
                discovery_info.advertisement, format_mac(discovery_info.address)
            )
        ):
            return None
        LOGGER.debug(
            "Device %s (%s) detected as '%s'",
            discovery_info.name,
            format_mac(discovery_info.address),
            bms_class.bms_id(),
        )
        return str(bms_class.get_bms_module())

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        LOGGER.debug("Bluetooth device detected: %s", discovery_info)

        address: Final[str] = format_mac(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        if not (bms_module := await self._async_device_supported(discovery_info)):
            return self.async_abort(reason="not_supported")

        self._disc_dev = ConfigFlow.DiscoveredDevice(
            discovery_info.name, discovery_info, bms_module
        )
        self.context["title_placeholders"] = {
            CONF_NAME: self._disc_dev.name,
            CONF_ID: address[8:],  # remove OUI
            CONF_MODEL: self._disc_dev.model(),
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth device discovery."""
        assert self._disc_dev is not None
        LOGGER.debug("confirm step for %s", self._disc_dev.name)

        if user_input is not None:
            return self.async_create_entry(
                title=self._disc_dev.name,
                data={"type": self._disc_dev.type},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context.get("title_placeholders"),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        LOGGER.debug(
            f"step user for {user_input[CONF_ADDRESS] if user_input else 'selection'}"
        )

        if user_input is not None:
            address: str = format_mac(user_input[CONF_ADDRESS])
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._disc_dev = self._disc_devs[address]

            return self.async_create_entry(
                title=self._disc_dev.name,
                data={"type": self._disc_dev.type},
            )

        current_addresses: Final[set[str | None]] = self._async_current_ids(
            include_ignore=False
        )
        for discovery_info in async_discovered_service_info(
            self.hass, connectable=True
        ):
            address = format_mac(discovery_info.address)
            if address in current_addresses or address in self._disc_devs:
                continue
            if not (bms_module := await self._async_device_supported(discovery_info)):
                continue

            self._disc_devs[address] = ConfigFlow.DiscoveredDevice(
                discovery_info.name, discovery_info, bms_module
            )

        if not self._disc_devs:
            return self.async_abort(reason="no_devices_found")

        devices: list[SelectOptionDict] = []
        for address, discovery in self._disc_devs.items():
            devices.append(
                SelectOptionDict(
                    value=address,
                    label=f"{discovery.name} ({address}) - {discovery.model()}",
                )
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(options=devices),
                    )
                }
            ),
        )
