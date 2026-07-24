"""Config flow for Gardena Bluetooth integration."""

import logging
from typing import Any, override

from gardena_bluetooth.client import Client
from gardena_bluetooth.const import PRODUCT_NAMES, DeviceInformation
from gardena_bluetooth.exceptions import CharacteristicNotFound, CommunicationFailure
from gardena_bluetooth.parse import ManufacturerData, ProductType
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import AbortFlow

from . import async_get_product, async_get_products, get_connection
from .const import CONF_PRODUCT_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)

_SUPPORTED_PRODUCT_TYPES = {
    ProductType.PUMP,
    ProductType.VALVE,
    ProductType.WATER_COMPUTER,
    ProductType.AUTOMATS,
    ProductType.PRESSURE_TANKS,
    ProductType.AQUA_CONTOURS,
}


class GardenaBluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gardena Bluetooth."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.address: str | None
        self.devices: dict[str, ManufacturerData] = {}

    async def async_read_data(self):
        """Try to connect to device and extract information."""
        assert self.address
        client = Client(get_connection(self.hass, self.address))
        try:
            model = await client.read_char(DeviceInformation.model_number)
            _LOGGER.debug("Found device with model: %s", model)
        except (CharacteristicNotFound, CommunicationFailure) as exception:
            raise AbortFlow(
                "cannot_connect", description_placeholders={"error": str(exception)}
            ) from exception
        finally:
            await client.disconnect()

        assert self.address in self.devices
        return {
            CONF_ADDRESS: self.address,
            CONF_PRODUCT_TYPE: self.devices[self.address].product_type.name,
        }

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered device: %s", discovery_info)

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        mfg = await async_get_product(self.hass, discovery_info.address)
        self.devices[discovery_info.address] = mfg
        if mfg.product_type not in _SUPPORTED_PRODUCT_TYPES:
            return self.async_abort(reason="no_devices_found")

        self.address = discovery_info.address
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.address
        title = PRODUCT_NAMES[self.devices[self.address].product_type]

        if user_input is not None:
            data = await self.async_read_data()
            return self.async_create_entry(title=title, data=data)

        self.context["title_placeholders"] = {
            "name": title,
        }

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()

        current = self._async_current_ids(include_ignore=False)
        self.devices = await async_get_products(self.hass)

        # Keep selection sorted by address to ensure stable tests
        devices = {
            address: PRODUCT_NAMES[data.product_type]
            for address in sorted(self.devices)
            if address not in current
            and (data := self.devices[address]).product_type in _SUPPORTED_PRODUCT_TYPES
        }

        if not devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(devices),
                },
            ),
        )
