"""Config flow for Mammotion Luba."""

from typing import TYPE_CHECKING, Any

from aiohttp.web_exceptions import HTTPException
from bleak.backends.device import BLEDevice
from pymammotion.aliyun.cloud_gateway import CloudIOTGateway
from pymammotion.http.http import MammotionHTTP
from pymammotion.mammotion.devices.mammotion import Mammotion
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, format_mac

from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    CONF_BLE_DEVICES,
    CONF_DEVICE_NAME,
    CONF_STAY_CONNECTED_BLUETOOTH,
    CONF_USE_WIFI,
    DEVICE_SUPPORT,
    DOMAIN,
    LOGGER,
)


class MammotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mammotion."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}
        self._stay_connected = False
        self._cloud_client: CloudIOTGateway | None = None
        self._discovered_device: BLEDevice | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo | None = None
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        if discovery_info is None:
            return self.async_abort(reason="no_devices_found")

        device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )

        if device is None:
            return self.async_abort(reason="no_longer_present")

        if device.name is None or not device.name.startswith(DEVICE_SUPPORT):
            return self.async_abort(reason="not_supported")

        self.context["title_placeholders"] = {"name": device.name}

        self._discovered_device = device

        await self.async_set_unique_id(discovery_info.name)
        self._abort_if_unique_id_configured(
            updates={CONF_ADDRESS: discovery_info.address}
        )

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""

        assert self._discovered_device
        ble_devices: dict[str, str] = {
            self._discovered_device.name: self._discovered_device.address
        }
        self._config = {
            CONF_BLE_DEVICES: ble_devices,
            CONF_ADDRESS: self._discovered_device.address,
        }

        try:
            # Look for account-based configurations
            device_registry = dr.async_get(self.hass)
            current_entries = self.hass.config_entries.async_entries(DOMAIN)

            for entry in current_entries:
                if not entry.data.get(CONF_ACCOUNT_ID):
                    continue

                device_entries = dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                )

                for device in device_entries:
                    # Check both MAC address and any other identifiers
                    identifiers = {id[1] for id in device.identifiers}
                    if device.name in identifiers:
                        # Found matching device in account
                        if entry.state == config_entries.ConfigEntryState.LOADED:
                            # # Update existing entry with BLE info

                            formatted_ble = format_mac(self._discovered_device.address)

                            device_registry.async_update_device(
                                device.id,
                                connections={(CONNECTION_BLUETOOTH, formatted_ble)},
                            )
                            # reload the entry now we have a ble address
                            self.hass.config_entries.async_schedule_reload(
                                entry.entry_id
                            )
                            return self.async_show_form(
                                step_id="bluetooth_confirm",
                                last_step=True,
                                description_placeholders={
                                    "name": self._discovered_device.name
                                },
                            )

                        # Entry exists but not loaded
                        return self.async_abort(reason="existing_account_not_loaded")

        except Exception as ex:
            # _LOGGER.exception("Error checking for existing account")
            raise ConfigEntryNotReady from ex

        if user_input is not None:
            return await self.async_step_wifi(user_input)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            last_step=False,
            description_placeholders={"name": self._discovered_device.name},
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_STAY_CONNECTED_BLUETOOTH,
                        default=False,
                    ): cv.boolean
                },
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS) or self._config.get(CONF_ADDRESS)
            if address is not None:
                self._config = {
                    CONF_ADDRESS: address,
                }
                self._stay_connected = user_input.get(
                    CONF_STAY_CONNECTED_BLUETOOTH, False
                )

                self._discovered_device = bluetooth.async_ble_device_from_address(
                    self.hass, address
                )

            return await self.async_step_wifi(user_input)

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            name = discovery_info.name
            if address in current_addresses or address in self._discovered_devices:
                continue
            if name is None or not name.startswith(DEVICE_SUPPORT):
                continue
            if self.hass.config_entries.async_entry_for_domain_unique_id(
                self.handler, name
            ):
                continue

            self._discovered_devices[address] = discovery_info.name

        if not self._discovered_devices:
            return await self.async_step_wifi(user_input)

        return self.async_show_form(
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ADDRESS): vol.In(self._discovered_devices),
                    vol.Optional(
                        CONF_STAY_CONNECTED_BLUETOOTH,
                        default=False,
                    ): cv.boolean,
                },
            ),
        )

    async def async_step_wifi(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Handle the user step for Wi-Fi control."""
        if user_input is not None and (
            user_input.get(CONF_ACCOUNTNAME) is not None
            or user_input.get(CONF_USE_WIFI) is True
        ):
            account = user_input.get(CONF_ACCOUNTNAME, "")
            password = user_input.get(CONF_PASSWORD, "")
            mammotion_http = MammotionHTTP()

            try:
                await mammotion_http.login(account, password)
                if mammotion_http.login_info is None:
                    return self.async_abort(reason=str(mammotion_http.msg))
            except HTTPException as err:
                return self.async_abort(reason=str(err))

            user_account = mammotion_http.login_info.userInformation.userAccount

            await self.async_set_unique_id(user_account, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=account,
                data={
                    CONF_ACCOUNTNAME: account,
                    CONF_PASSWORD: password,
                    CONF_ACCOUNT_ID: user_account,
                    CONF_DEVICE_NAME: self._discovered_device.name
                    if self._discovered_device
                    else None,
                    CONF_USE_WIFI: user_input.get(CONF_USE_WIFI, True),
                    **self._config,
                },
                options={CONF_STAY_CONNECTED_BLUETOOTH: self._stay_connected},
            )

        if user_input is not None and user_input.get(CONF_USE_WIFI) is False:
            return self.async_create_entry(
                title=self._discovered_device.name,
                data={
                    CONF_ADDRESS: self._discovered_device.address,
                    CONF_USE_WIFI: user_input.get(CONF_USE_WIFI),
                },
                options={CONF_STAY_CONNECTED_BLUETOOTH: self._stay_connected},
            )

        schema = {
            vol.Optional(CONF_ACCOUNTNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_USE_WIFI, default=True): cv.boolean,
        }

        return self.async_show_form(step_id="wifi", data_schema=vol.Schema(schema))

    async def async_step_wifi_confirm(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Confirm device discovery."""

        address = self._config.get(CONF_ADDRESS)
        name = self._discovered_devices.get(address)
        mammotion = Mammotion()

        if user_input is not None:
            account = user_input.get(CONF_ACCOUNTNAME)
            password = user_input.get(CONF_PASSWORD)

            if self._cloud_client is None:
                try:
                    if mammotion.mqtt_list.get(account) is None:
                        self._cloud_client = await Mammotion().login(account, password)
                    else:
                        self._cloud_client = mammotion.mqtt_list.get(
                            account
                        ).cloud_client
                except HTTPException as err:
                    return self.async_abort(reason=str(err))
            user_account = (
                self._cloud_client.mammotion_http.login_info.userInformation.userAccount
            )

            await self.async_set_unique_id(user_account, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_account,
                data={
                    CONF_ACCOUNTNAME: account,
                    CONF_PASSWORD: password,
                    CONF_DEVICE_NAME: name,
                    CONF_USE_WIFI: user_input.get(CONF_USE_WIFI, True),
                    **self._config,
                },
                options={CONF_STAY_CONNECTED_BLUETOOTH: self._stay_connected},
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
            return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STAY_CONNECTED_BLUETOOTH,
                    default=self.config_entry.options.get(
                        CONF_STAY_CONNECTED_BLUETOOTH, False
                    ),
                ): cv.boolean
            }
        )

        return self.async_show_form(
            data_schema=options_schema,
        )
