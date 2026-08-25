"""Config flow for Specialized Turbo bikes."""

from collections.abc import Callable, Mapping
from typing import Any, override

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from specialized_turbo import (
    BikeAdvertisement,
    BikeInfo,
    BLEProfile,
    DecryptionError,
    EncryptionKeyProviderError,
    EncryptionKeyRequiredError,
    IdentificationError,
    ProtocolEncryptionMethod,
    SpecializedConnection,
    WrappedKeyError,
    is_specialized_advertisement,
    parse_bike_advertisement,
    parse_bike_info,
    unwrap_keystore_key,
)
from specialized_turbo.cloud import CloudAuthenticationError, SpecializedCloudClient
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_HMI_HARDWARE,
    CONF_HMI_SERIAL,
    CONF_KEY_SOURCE,
    CONF_WRAPPED_KEY,
    DOMAIN,
    KEY_SOURCE_ACCOUNT,
    KEY_SOURCE_MANUAL,
)


class SpecializedTurboConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Specialized Turbo bikes."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str | None = None
        self._title = "Specialized Turbo"
        self._advertisement: BikeAdvertisement | None = None
        self._bike_info: BikeInfo | None = None
        self._target_entry_id: str | None = None

    async def _async_test_connection(self) -> bool:
        """Validate a legacy or advertisement-incomplete bike connection."""
        return await self._async_validate_connection()

    async def _async_validate_encrypted_connection(self, wrapped_key: str) -> bool:
        """Run the encrypted identification handshake before saving an entry."""
        return await self._async_validate_connection(wrapped_key)

    async def _async_validate_connection(
        self,
        wrapped_key: str | None = None,
    ) -> bool:
        """Run upstream connection setup with Home Assistant's BLE client."""
        assert self._address is not None
        address = self._address
        ble_device = async_ble_device_from_address(
            self.hass,
            address,
            connectable=True,
        )
        if ble_device is None:
            return False

        async def client_factory(
            address_or_device: str | BLEDevice,
            disconnected_callback: Callable[[BleakClient], None] | None,
        ) -> BleakClient:
            assert isinstance(address_or_device, BLEDevice)
            return await establish_connection(
                BleakClient,
                address_or_device,
                address,
                disconnected_callback=disconnected_callback,
            )

        connection = SpecializedConnection(
            ble_device,
            advertisement=self._advertisement,
            bike_info=self._bike_info,
            wrapped_key=wrapped_key,
            discovery_timeout=0,
            client_factory=client_factory,
        )
        try:
            await connection.connect()
        except (
            DecryptionError,
            EncryptionKeyProviderError,
            EncryptionKeyRequiredError,
        ):
            raise
        except (
            BleakError,
            IdentificationError,
            TimeoutError,
            RuntimeError,
            ValueError,
        ):
            return False
        finally:
            await connection.disconnect()
        return True

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._set_device(discovery_info)
        self.context["title_placeholders"] = {
            "name": self._title,
            "address": discovery_info.address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery and collect encryption key choices."""
        assert self._discovery_info is not None
        return await self._async_device_form(
            "bluetooth_confirm",
            user_input,
            include_address=False,
        )

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._set_device(self._discovered_devices[address])
            return await self._async_device_form(
                "user",
                user_input,
                include_address=True,
            )

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if format_mac(info.address) in current_addresses:
                continue
            if _is_specialized_service_info(info):
                self._discovered_devices[info.address] = info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=self._device_schema(include_address=True),
        )

    async def _async_device_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        *,
        include_address: bool,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._requires_encryption:
                return await self.async_step_key_source()
            try:
                valid = await self._async_test_connection()
            except EncryptionKeyRequiredError:
                errors["base"] = "key_unavailable"
            else:
                if valid:
                    return self._create_or_update_entry({})
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id=step_id,
            data_schema=self._device_schema(include_address=include_address),
            description_placeholders={
                "name": self._title,
                "address": self._address or "",
            },
            errors=errors,
        )

    async def async_step_key_source(
        self,
        _user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose automatic account lookup or manual wrapped key."""
        return self.async_show_menu(
            step_id="key_source",
            menu_options=["account", "manual_key"],
        )

    async def async_step_account(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Fetch the bike key using Specialized account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                wrapped_key = await self._async_fetch_account_key(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                if not await self._async_validate_encrypted_connection(wrapped_key):
                    errors["base"] = "cannot_connect"
                else:
                    return self._create_or_update_entry(
                        {
                            CONF_KEY_SOURCE: KEY_SOURCE_ACCOUNT,
                            CONF_WRAPPED_KEY: wrapped_key,
                        }
                    )
            except CloudAuthenticationError:
                errors["base"] = "invalid_auth"
            except (
                DecryptionError,
                EncryptionKeyProviderError,
                EncryptionKeyRequiredError,
            ):
                errors["base"] = "key_unavailable"

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_manual_key(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Accept a wrapped key obtained outside Home Assistant."""
        errors: dict[str, str] = {}
        if user_input is not None:
            wrapped_key = user_input[CONF_WRAPPED_KEY].strip()
            try:
                unwrap_keystore_key(wrapped_key)
            except WrappedKeyError:
                errors["base"] = "invalid_wrapped_key"
            else:
                try:
                    valid = await self._async_validate_encrypted_connection(wrapped_key)
                except (
                    DecryptionError,
                    EncryptionKeyProviderError,
                    EncryptionKeyRequiredError,
                ):
                    errors["base"] = "invalid_wrapped_key"
                else:
                    if valid:
                        return self._create_or_update_entry(
                            {
                                CONF_KEY_SOURCE: KEY_SOURCE_MANUAL,
                                CONF_WRAPPED_KEY: wrapped_key,
                            }
                        )
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual_key",
            data_schema=vol.Schema({vol.Required(CONF_WRAPPED_KEY): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Start reauthentication for an encrypted existing entry."""
        del entry_data
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        self._target_entry_id = entry.entry_id
        self._address = entry.data[CONF_ADDRESS]
        self._title = entry.title
        hmi_hardware = entry.data.get(CONF_HMI_HARDWARE)
        hmi_serial = entry.data.get(CONF_HMI_SERIAL)
        if hmi_hardware is not None and hmi_serial is not None:
            self._advertisement = BikeAdvertisement(
                generation=BLEProfile.TCX,
                encryption=ProtocolEncryptionMethod.AES_CTR,
                hmi_hardware=hmi_hardware,
                hmi_serial=hmi_serial,
            )
        return await self.async_step_key_source()

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Replace the wrapped key for an encrypted bike."""
        del user_input
        entry = self._get_reconfigure_entry()
        hmi_hardware = entry.data.get(CONF_HMI_HARDWARE)
        hmi_serial = entry.data.get(CONF_HMI_SERIAL)
        if hmi_hardware is None or hmi_serial is None:
            return self.async_abort(reason="not_encrypted")
        self._target_entry_id = entry.entry_id
        self._address = entry.data[CONF_ADDRESS]
        self._title = entry.title
        self._advertisement = BikeAdvertisement(
            generation=BLEProfile.TCX,
            encryption=ProtocolEncryptionMethod.AES_CTR,
            hmi_hardware=hmi_hardware,
            hmi_serial=hmi_serial,
        )
        return await self.async_step_key_source()

    async def _async_fetch_account_key(self, email: str, password: str) -> str:
        """Fetch a wrapped key with Home Assistant's managed HTTP client."""
        assert self._advertisement is not None
        assert self._advertisement.hmi_hardware is not None
        assert self._advertisement.hmi_serial is not None
        cloud = SpecializedCloudClient(client=get_async_client(self.hass))
        await cloud.login(email, password)
        return await cloud.get_wrapped_key(
            hmi_hardware=self._advertisement.hmi_hardware,
            hmi_serial=self._advertisement.hmi_serial,
        )

    def _set_device(self, info: BluetoothServiceInfoBleak) -> None:
        """Store discovery data for the selected bike."""
        self._discovery_info = info
        self._address = info.address
        self._title = info.name or "Specialized Turbo"
        self._advertisement = parse_bike_advertisement(
            info.manufacturer_data,
            local_name=info.name,
            service_uuids=info.service_uuids,
        )
        self._bike_info = parse_bike_info(
            info.name or "",
            info.manufacturer_data,
        )

    @property
    def _requires_encryption(self) -> bool:
        return (
            self._advertisement is not None
            and self._advertisement.encryption == ProtocolEncryptionMethod.AES_CTR
        )

    def _device_schema(self, *, include_address: bool) -> vol.Schema:
        fields: dict[vol.Marker, Any] = {}
        if include_address:
            fields[vol.Required(CONF_ADDRESS)] = vol.In(
                {
                    address: f"{info.name or 'Specialized Turbo'} ({address})"
                    for address, info in self._discovered_devices.items()
                }
            )
        return vol.Schema(fields)

    def _create_or_update_entry(
        self,
        key_data: dict[str, Any],
    ) -> ConfigFlowResult:
        assert self._address is not None
        data: dict[str, Any] = {
            CONF_ADDRESS: self._address,
            **key_data,
        }
        if self._advertisement is not None:
            if self._advertisement.hmi_hardware is not None:
                data[CONF_HMI_HARDWARE] = self._advertisement.hmi_hardware
            if self._advertisement.hmi_serial is not None:
                data[CONF_HMI_SERIAL] = self._advertisement.hmi_serial

        if self._target_entry_id is not None:
            entry = self.hass.config_entries.async_get_entry(self._target_entry_id)
            assert entry is not None
            return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_create_entry(title=self._title, data=data)


def _is_specialized_service_info(info: BluetoothServiceInfoBleak) -> bool:
    """Check whether service information belongs to a Specialized bike."""
    return is_specialized_advertisement(
        info.manufacturer_data,
        local_name=info.name,
        service_uuids=info.service_uuids,
    )
