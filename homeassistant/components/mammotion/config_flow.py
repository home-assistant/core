"""Config flow for Mammotion."""

from collections.abc import Mapping
from typing import Any, override

from aiohttp import ClientError
from bleak.backends.device import BLEDevice
import probatio
from pymammotion.http.http import MammotionHTTP

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, format_mac

from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    CONF_BLE_DEVICES,
    DEVICE_SUPPORT,
    DOMAIN,
    LOGGER,
)


def _with_ble_address(entry: ConfigEntry, device: BLEDevice) -> dict[str, str]:
    """Return the entry's Bluetooth addresses with the discovered one recorded."""
    return {
        **entry.data.get(CONF_BLE_DEVICES, {}),
        device.name: format_mac(device.address),
    }


class MammotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mammotion."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}
        self._discovered_devices: dict[str, str] = {}
        self._discovered_device: BLEDevice | None = None

    def _find_bluetooth_device(
        self, device: BLEDevice
    ) -> tuple[ConfigEntry, dr.DeviceEntry] | None:
        """Return the entry and device entry owning this mower, if configured."""
        device_registry = dr.async_get(self.hass)

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if not entry.data.get(CONF_ACCOUNT_ID):
                continue

            for device_entry in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            ):
                identifiers = {device_id[1] for device_id in device_entry.identifiers}
                if device.name in identifiers:
                    return entry, device_entry
        return None

    async def check_and_update_bluetooth_device(
        self, device: BLEDevice
    ) -> ConfigEntry | None:
        """Check if the device is already configured and update ble mac if needed."""
        if (found := self._find_bluetooth_device(device)) is None:
            return None

        entry, device_entry = found
        await self.async_set_unique_id(entry.data.get(CONF_ACCOUNT_ID))
        formatted_ble = format_mac(device.address) if device else None

        if (
            CONNECTION_BLUETOOTH,
            formatted_ble,
        ) not in device_entry.connections and formatted_ble is not None:
            dr.async_get(self.hass).async_update_device(
                device_entry.id,
                new_connections=device_entry.connections
                | {(CONNECTION_BLUETOOTH, formatted_ble)},
            )
            if entry.state is config_entries.ConfigEntryState.LOADED:
                # reload the entry now we have a ble address
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return entry

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        LOGGER.debug("Discovered bluetooth device: %s", discovery_info)

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )

        if device is None:
            return self.async_abort(reason="no_longer_present")

        if device.name is None or not device.name.startswith(DEVICE_SUPPORT):
            return self.async_abort(reason="not_supported")

        self.context["title_placeholders"] = {"name": device.name}

        self._discovered_device = device

        if entry := await self.check_and_update_bluetooth_device(device):
            self._abort_if_unique_id_configured(
                updates={CONF_BLE_DEVICES: _with_ble_address(entry, device)},
                reload_on_update=False,
            )

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""

        assert self._discovered_device is not None
        assert self._discovered_device.name is not None
        device = self._discovered_device
        name = device.name or ""
        if entry := await self.check_and_update_bluetooth_device(device):
            self._abort_if_unique_id_configured(
                updates={CONF_BLE_DEVICES: _with_ble_address(entry, device)},
                reload_on_update=False,
            )

        ble_devices: dict[str, str] = {name: format_mac(device.address)}
        self._config = {
            CONF_BLE_DEVICES: ble_devices,
        }

        if user_input is not None:
            return await self.async_step_wifi()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""

        if user_input is not None:
            if address := user_input.get(CONF_ADDRESS):
                self._config = {
                    CONF_BLE_DEVICES: {
                        self._discovered_devices[address]: format_mac(address)
                    }
                }
            return await self.async_step_wifi()

        # Ignored discoveries count too, so a dismissed mower is not offered again.
        current_ids = {format_mac(uid) for uid in self._async_current_ids() if uid}
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            name = discovery_info.name
            if format_mac(address) in current_ids:
                continue
            if name is None or not name.startswith(DEVICE_SUPPORT):
                continue

            device = bluetooth.async_ble_device_from_address(
                self.hass, discovery_info.address
            )

            if device and self._find_bluetooth_device(device) is None:
                self._discovered_devices[address] = discovery_info.name

        if not self._discovered_devices:
            return await self.async_step_wifi()

        return self.async_show_form(
            last_step=False,
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_ADDRESS): probatio.In(
                        self._discovered_devices
                    ),
                },
            ),
            step_id="user",
        )

    def _account_configured(
        self, account: str, exclude_entry_id: str | None = None
    ) -> bool:
        """Return whether another entry already holds this account name or ID."""
        account = account.casefold()
        return any(
            account
            in (
                entry.data[CONF_ACCOUNTNAME].casefold(),
                entry.data[CONF_ACCOUNT_ID].casefold(),
            )
            for entry in self._async_current_entries(include_ignore=False)
            if entry.entry_id != exclude_entry_id
        )

    async def _async_validate_login(
        self, account: str, password: str
    ) -> tuple[dict[str, str], str | None]:
        """Validate the credentials and return errors and the account ID."""
        errors: dict[str, str] = {}
        mammotion_http = MammotionHTTP(
            account, password, session=async_get_clientsession(self.hass)
        )

        try:
            await mammotion_http.login_v2(account, password)
        except (ClientError, OSError) as err:
            LOGGER.debug("Cannot connect: %s", err)
            errors["base"] = "cannot_connect"
            return errors, None
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return errors, None

        if (login_info := mammotion_http.login_info) is None:
            errors["base"] = "invalid_auth"
            return errors, None

        return errors, login_info.userInformation.userAccount

    async def async_step_wifi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step for Wi-Fi control."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNTNAME]
            password = user_input[CONF_PASSWORD]
            # A login supersedes the account's cloud session, which the
            # configured entry is still using.
            if self._account_configured(account):
                return self.async_abort(reason="already_configured")
            errors, user_account = await self._async_validate_login(account, password)

            if not errors:
                await self.async_set_unique_id(user_account, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=account,
                    data={
                        CONF_ACCOUNTNAME: account,
                        CONF_PASSWORD: password,
                        CONF_ACCOUNT_ID: user_account,
                        **self._config,
                    },
                )

        schema = {
            probatio.Required(CONF_ACCOUNTNAME): cv.string,
            probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        }

        return self.async_show_form(
            step_id="wifi", data_schema=probatio.Schema(schema), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication after the cloud rejected our credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            account = entry.data[CONF_ACCOUNTNAME]
            password = user_input[CONF_PASSWORD]
            errors, user_account = await self._async_validate_login(account, password)

            if not errors:
                await self.async_set_unique_id(user_account)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string}
            ),
            description_placeholders={"account_name": entry.data[CONF_ACCOUNTNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNTNAME]
            password = user_input[CONF_PASSWORD]
            # Logging in would supersede the cloud session of the entry holding it.
            if self._account_configured(account, exclude_entry_id=entry.entry_id):
                return self.async_abort(reason="already_configured")
            errors, user_account = await self._async_validate_login(account, password)

            if not errors:
                await self.async_set_unique_id(user_account)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCOUNTNAME: account,
                        CONF_PASSWORD: password,
                        CONF_ACCOUNT_ID: user_account,
                    },
                )

        # No default for the password, which would send it to the browser.
        schema = probatio.Schema(
            {
                probatio.Required(CONF_ACCOUNTNAME): cv.string,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_ACCOUNTNAME: entry.data[CONF_ACCOUNTNAME]}
            ),
            errors=errors,
        )
