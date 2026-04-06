"""Config flow for OpenDisplay integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from opendisplay import (
    MANUFACTURER_ID,
    AuthenticationFailedError,
    AuthenticationRequiredError,
    BLEConnectionError,
    OpenDisplayDevice,
    OpenDisplayError,
)
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_ENCRYPTION_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


_ENCRYPTION_KEY_VALIDATOR = vol.All(str.strip, str.lower, vol.Match(r"^[0-9a-f]{32}$"))


class OpenDisplayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenDisplay."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_test_connection(
        self, address: str, encryption_key: bytes | None = None
    ) -> None:
        """Connect to the device and verify it responds."""
        ble_device = async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            raise BLEConnectionError(f"Could not find connectable device for {address}")

        async with OpenDisplayDevice(
            mac_address=address, ble_device=ble_device, encryption_key=encryption_key
        ) as device:
            await device.read_firmware_version()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}

        try:
            await self._async_test_connection(discovery_info.address)
        except AuthenticationRequiredError:
            return await self.async_step_encryption_key()
        except OpenDisplayError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error")
            return self.async_abort(reason="unknown")

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders=self.context["title_placeholders"],
            )

        return self.async_create_entry(title=self._discovery_info.name, data={})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                await self._async_test_connection(address)
            except AuthenticationRequiredError:
                self.context["title_placeholders"] = {
                    "name": self._discovered_devices[address].name
                }
                return await self.async_step_encryption_key()
            except OpenDisplayError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self._discovered_devices[address].name,
                    data={},
                )
        else:
            current_addresses = self._async_current_ids(include_ignore=False)
            for discovery_info in async_discovered_service_info(self.hass):
                address = discovery_info.address
                if address in current_addresses or address in self._discovered_devices:
                    continue
                if MANUFACTURER_ID in discovery_info.manufacturer_data:
                    self._discovered_devices[address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            addr: f"{info.name} ({addr})"
                            for addr, info in self._discovered_devices.items()
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def _async_try_connection(
        self,
        address: str,
        encryption_key: bytes | None,
        errors: dict[str, str],
    ) -> bool:
        """Test connection, populate errors, and return True on success."""
        try:
            await self._async_test_connection(address, encryption_key)
        except AuthenticationFailedError, AuthenticationRequiredError:
            errors[CONF_ENCRYPTION_KEY] = "invalid_auth"
        except OpenDisplayError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error")
            errors["base"] = "unknown"
        else:
            return True
        return False

    async def async_step_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the encryption key step."""
        errors: dict[str, str] = {}
        name: str = self.context["title_placeholders"]["name"]

        if user_input is not None:
            try:
                key: str = _ENCRYPTION_KEY_VALIDATOR(user_input[CONF_ENCRYPTION_KEY])
            except vol.Invalid:
                errors[CONF_ENCRYPTION_KEY] = "invalid_key_format"
            else:
                if TYPE_CHECKING:
                    assert self.unique_id is not None
                if await self._async_try_connection(
                    self.unique_id, bytes.fromhex(key), errors
                ):
                    return self.async_create_entry(
                        title=name,
                        data={CONF_ENCRYPTION_KEY: key},
                    )

        return self.async_show_form(
            step_id="encryption_key",
            data_schema=vol.Schema({vol.Required(CONF_ENCRYPTION_KEY): str}),
            description_placeholders={"name": name},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            key: str | None = None
            if user_input[CONF_ENCRYPTION_KEY].strip():
                try:
                    key = _ENCRYPTION_KEY_VALIDATOR(user_input[CONF_ENCRYPTION_KEY])
                except vol.Invalid:
                    errors[CONF_ENCRYPTION_KEY] = "invalid_key_format"

            if not errors:
                address = reauth_entry.unique_id
                if TYPE_CHECKING:
                    assert address is not None
                if await self._async_try_connection(
                    address, bytes.fromhex(key) if key is not None else None, errors
                ):
                    new_data = dict(reauth_entry.data)
                    if key is not None:
                        new_data[CONF_ENCRYPTION_KEY] = key
                    else:
                        new_data.pop(CONF_ENCRYPTION_KEY, None)
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data=new_data,
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_ENCRYPTION_KEY, default=""): str}
            ),
            description_placeholders={"name": reauth_entry.title},
            errors=errors,
        )
