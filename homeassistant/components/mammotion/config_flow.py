"""Config flow for Mammotion Luba."""

from typing import Any, TYPE_CHECKING

import voluptuous as vol
from bleak import BLEDevice
from homeassistant.helpers.selector import (
    SelectSelectorConfig,
    SelectOptionDict,
    SelectSelectorMode,
    SelectSelector,
)
from pymammotion.http.http import connect_http
from pymammotion.mammotion.devices.mammotion import Mammotion

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
    ConfigEntry,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import callback

from homeassistant.helpers import config_validation as cv

from .const import (
    DEVICE_SUPPORT,
    DOMAIN,
    LOGGER,
    CONF_USE_WIFI,
    CONF_STAY_CONNECTED_BLUETOOTH,
    CONF_ACCOUNTNAME,
    CONF_DEVICE_NAME,
)


class MammotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mammotion."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config = {}
        self._discovered_device: BLEDevice | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        if discovery_info is None:
            return self.async_abort(reason="no_device")

        await self.async_set_unique_id(discovery_info.name)
        self._abort_if_unique_id_configured(
            updates={CONF_ADDRESS: discovery_info.address}
        )

        device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )

        if device is None:
            return self.async_abort(reason="no_longer_present")

        if device.name is None or not device.name.startswith(DEVICE_SUPPORT):
            return self.async_abort(reason="not_supported")

        self.context["title_placeholders"] = {"name": device.name}

        self._discovered_device = device

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""

        assert self._discovered_device

        self._config = {
            CONF_ADDRESS: self._discovered_device.address,
        }

        if user_input is not None:
            return await self.async_step_wifi(user_input)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            last_step=False,
            description_placeholders={"name": self._discovered_device.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS) or self._config.get(CONF_ADDRESS)
            if address is not None:
                name = self._discovered_devices.get(address)
                if name is None:
                    return self.async_abort(reason="no_longer_present")

                await self.async_set_unique_id(name, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                self._config = {
                    CONF_ADDRESS: address,
                }

            self._discovered_device = bluetooth.async_ble_device_from_address(self.hass, address)

            return await self.async_step_wifi(user_input)

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            name = discovery_info.name
            if address in current_addresses or address in self._discovered_devices:
                continue
            if name is None or not name.startswith(DEVICE_SUPPORT):
                continue
            self._discovered_devices[address] = discovery_info.name

        if not self._discovered_devices:
            return await self.async_step_wifi(user_input)

        return self.async_show_form(
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ADDRESS): vol.In(self._discovered_devices),
                },
            ),
        )

    async def async_step_wifi(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the user step for Wi-Fi control."""
        if user_input is not None and (
            user_input.get(CONF_ACCOUNTNAME) is not None
            or user_input.get(CONF_USE_WIFI) is True
        ):
            account = user_input.get(CONF_ACCOUNTNAME)
            password = user_input.get(CONF_PASSWORD)

            try:
                response = await connect_http(account, password)
                if response.login_info is None:
                    return self.async_abort(reason=str(response.msg))
            except Exception as err:
                return self.async_abort(reason=str(err))

            return await self.async_step_wifi_confirm(user_input)

        if user_input is not None and user_input.get(CONF_USE_WIFI) is False:
            return self.async_create_entry(
                title=self._discovered_device.name,
                data={CONF_ADDRESS: self._discovered_device.address},
            )

        schema = {
            vol.Optional(CONF_ACCOUNTNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_USE_WIFI, default=True): cv.boolean,
        }

        if self._config.get(CONF_ADDRESS) is None:
            schema = {
                vol.Required(CONF_ACCOUNTNAME): vol.All(cv.string, vol.Strip),
                vol.Required(CONF_PASSWORD): vol.All(cv.string, vol.Strip),
            }

        return self.async_show_form(step_id="wifi", data_schema=vol.Schema(schema))

    async def async_step_wifi_confirm(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Confirm device discovery."""

        device_name = user_input.get(CONF_DEVICE_NAME)
        address = self._config.get(CONF_ADDRESS)
        name = self._discovered_devices.get(address)

        if user_input is not None and (device_name or name):
            account = user_input.get(CONF_ACCOUNTNAME)
            password = user_input.get(CONF_PASSWORD)

            if name:
                cloud_client = await Mammotion.login(account, password)
                devices = cloud_client.get_devices_by_account_response().data.data
                found_device = [
                    device for device in devices if device.deviceName == name
                ]
                if not found_device:
                    return self.async_abort(
                        reason=f"{device_name or name} not found in account: {account}"
                    )

            await self.async_set_unique_id(device_name or name, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name or device_name,
                data={
                    CONF_ACCOUNTNAME: account,
                    CONF_PASSWORD: password,
                    CONF_DEVICE_NAME: name or device_name,
                    **self._config,
                },
            )

        account = user_input.get(CONF_ACCOUNTNAME)
        password = user_input.get(CONF_PASSWORD)
        self._config = {
            **self._config,
            **user_input,
        }
        cloud_client = await Mammotion.login(account, password)

        mowing_devices = [
            dev
            for dev in cloud_client.get_devices_by_account_response().data.data
            if (dev.productModel is None or dev.productModel != "ReferenceStation")
        ]

        machine_options = [
            SelectOptionDict(
                value=device.deviceName,
                label=device.deviceName,
            )
            for device in mowing_devices
        ]

        machine_selection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_NAME, default=machine_options[0]["value"]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=machine_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="wifi_confirm", data_schema=machine_selection_schema
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return MammotionConfigFlowHandler(config_entry)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if TYPE_CHECKING:
            assert entry

        errors: dict[str, str] | None = None
        user_input = user_input or {}
        if user_input:
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        **user_input,
                    },
                    reason="reconfigure_successful",
                )

        schema = {
            vol.Required(
                CONF_ACCOUNTNAME, default=entry.data.get(CONF_ACCOUNTNAME)
            ): cv.string,
            vol.Required(
                CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD)
            ): cv.string,
            vol.Optional(
                CONF_USE_WIFI, default=entry.data.get(CONF_USE_WIFI, True)
            ): cv.boolean,
        }

        if user_input is not None and entry.data.get(CONF_ADDRESS) is None:
            schema = {
                vol.Required(
                    CONF_ACCOUNTNAME, default=entry.data.get(CONF_ACCOUNTNAME)
                ): vol.All(cv.string, vol.Strip),
                vol.Required(
                    CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD)
                ): vol.All(cv.string, vol.Strip),
            }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


class MammotionConfigFlowHandler(OptionsFlowWithConfigEntry):
    """Handles options flow for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for the custom component."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STAY_CONNECTED_BLUETOOTH,
                    default=self.options.get(CONF_STAY_CONNECTED_BLUETOOTH, False),
                ): cv.boolean
            }
        )

        return self.async_show_form(
            data_schema=options_schema,
        )
