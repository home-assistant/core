"""Config flow for Besen."""

import asyncio
from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from besen.client import BesenClient
from besen.const import DEFAULT_PIN
from besen.exceptions import (
    CannotConnect,
    CommandFailed,
    InvalidAuth,
    NoConnectablePath,
)
from besen.udp import BesenUdpClient
import probatio

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_SERIAL,
    CONF_TRANSPORT,
    DOMAIN,
    TRANSPORT_BLUETOOTH,
    TRANSPORT_LAN,
)
from .coordinator import (
    BesenConnectionState,
    async_get_connection_state,
    async_get_known_serial,
    async_is_serial_configured,
)
from .lan import async_acquire_udp_hub, async_release_udp_hub

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

    from homeassistant.config_entries import ConfigFlowResult

    from . import BesenConfigEntry
    from .coordinator import BesenCoordinator

_LOGGER = logging.getLogger(__name__)


class _AlreadyConfigured(Exception):
    """The charger already has an entry using another transport."""


def _normalize_address(address: str) -> str:
    """Normalize a Bluetooth address."""

    return address.strip().upper()


PIN_SCHEMA = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.PASSWORD,
    )
)

PIN_ONLY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PIN, default=DEFAULT_PIN): PIN_SCHEMA,
    }
)

REAUTH_SCHEMA = probatio.Schema({probatio.Required(CONF_PIN): PIN_SCHEMA})


def _user_schema(
    discoveries: dict[str, BluetoothServiceInfoBleak],
) -> probatio.Schema:
    """Return the user step schema."""

    return probatio.Schema(
        {
            probatio.Optional(CONF_ADDRESS): probatio.In(
                {
                    address: discovery.name or address
                    for address, discovery in discoveries.items()
                }
            ),
            probatio.Required(CONF_PIN, default=DEFAULT_PIN): PIN_SCHEMA,
            probatio.Optional(CONF_HOST): str,
        }
    )


async def _async_validate_input(
    hass: HomeAssistant,
    *,
    address: str,
    pin: str,
    name: str | None,
    connection: BesenConnectionState,
) -> tuple[str, str | None]:
    """Return the charger title and serial after verifying the connection."""

    if len(pin) != 6 or not (pin.isascii() and pin.isdecimal()):
        raise InvalidAuth("PIN must be exactly 6 digits")

    def _ble_device_provider() -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(
            hass,
            address,
            connectable=True,
        )

    if _ble_device_provider() is None:
        await bluetooth.async_request_active_scan(hass)

    if _ble_device_provider() is None:
        raise NoConnectablePath("No connectable Bluetooth path is available")

    client = BesenClient(
        address=address,
        pin=pin,
        ble_device_provider=_ble_device_provider,
        logger=_LOGGER,
        advertised_name=name,
    )

    async def stop_client() -> None:
        await client.async_stop()
        if client.is_connected:
            raise CannotConnect("Test connection was not released")

    connection.async_set_cleanup(stop_client)
    try:
        await client.async_start()
        info = client.state.info
    finally:
        await connection.async_cleanup()
    if info.serial and async_is_serial_configured(hass, info.serial, address=address):
        raise _AlreadyConfigured
    return info.model or name or address, info.serial


class BesenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Besen config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""

        self._discovered_address: str | None = None
        self._discovered_name: str | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._pending_data: dict[str, Any] = {}
        self._pending_title = "Besen"
        self._operation_task: asyncio.Task[None] | None = None
        self._operation_error: str | None = None
        self._operation_step = "lan"
        self._removed = False
        self._connection: BesenConnectionState | None = None

    async def _async_use_connection(self, connection: BesenConnectionState) -> None:
        """Release retained cleanup before switching validation ownership."""
        if self._connection is not None and self._connection is not connection:
            async with self._connection.lock:
                await self._connection.async_cleanup()
        self._connection = connection

    async def _async_validate_bluetooth(
        self, *, address: str, pin: str, name: str | None
    ) -> tuple[str, str | None]:
        """Retain Bluetooth cleanup on this flow until it has succeeded."""
        connection = async_get_connection_state(self.hass, f"bluetooth:{address}")
        await self._async_use_connection(connection)
        async with connection.lock:
            await connection.async_cleanup()
            return await _async_validate_input(
                self.hass, address=address, pin=pin, name=name, connection=connection
            )

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""

        if not (discovery_info.name or "").startswith("ACP#"):
            return self.async_abort(reason="not_supported")

        address = _normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured(
            updates={
                CONF_ADDRESS: address,
                CONF_NAME: discovery_info.name,
            }
        )
        self._discovered_address = address
        self._discovered_name = discovery_info.name
        self.context["title_placeholders"] = {
            "name": discovery_info.name or address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm a discovered charger."""

        assert self._discovered_address is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input[CONF_PIN]
            try:
                title, serial = await self._async_validate_bluetooth(
                    address=self._discovered_address,
                    pin=pin,
                    name=self._discovered_name,
                )
            except _AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath:
                errors["base"] = "no_connectable_path"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: self._discovered_address,
                        CONF_NAME: self._discovered_name,
                        CONF_PIN: pin,
                        CONF_SERIAL: serial,
                    },
                )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=PIN_ONLY_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_HOST):
                return await self.async_step_lan(user_input)
            if not user_input.get(CONF_ADDRESS):
                return self.async_show_form(
                    step_id="user",
                    data_schema=_user_schema(self._discovered_devices),
                    errors={"base": "choose_connection"},
                )
            address = user_input[CONF_ADDRESS]
            pin = user_input[CONF_PIN]
            discovery_info = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            try:
                title, serial = await self._async_validate_bluetooth(
                    address=address,
                    pin=pin,
                    name=discovery_info.name,
                )
            except _AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath:
                errors["base"] = "no_connectable_path"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: discovery_info.name,
                        CONF_PIN: pin,
                        CONF_SERIAL: serial,
                    },
                )

        if not self._discovered_devices:
            await bluetooth.async_request_active_scan(self.hass)
            current_addresses = self._async_current_ids(include_ignore=False)
            for discovery_info in async_discovered_service_info(self.hass):
                address = _normalize_address(discovery_info.address)
                if (
                    address in current_addresses
                    or address in self._discovered_devices
                    or not (discovery_info.name or "").startswith("ACP#")
                ):
                    continue
                self._discovered_devices[address] = discovery_info

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self._discovered_devices),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected PIN for an existing charger."""

        entry = self._get_reauth_entry()
        self._connection = async_get_connection_state(self.hass, entry.entry_id)
        self.context["title_placeholders"] = {"name": entry.title}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a replacement PIN without replacing the config entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input[CONF_PIN]
            if len(pin) != 6 or not (pin.isascii() and pin.isdecimal()):
                errors["base"] = "invalid_auth"
            else:
                self._pending_data = {**self._entry_data(entry), CONF_PIN: pin}
                self._operation_step = "reauth_confirm"
                transport = (
                    TRANSPORT_LAN
                    if entry.data.get(CONF_TRANSPORT) == TRANSPORT_LAN
                    else TRANSPORT_BLUETOOTH
                )
                return await self._start_operation(transport)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    def _current_entry(self) -> BesenConfigEntry | None:
        """Return the existing entry without changing its identity."""
        if self.source == config_entries.SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry()
        if self.source == config_entries.SOURCE_REAUTH:
            return self._get_reauth_entry()
        return None

    def _entry_data(self, entry: BesenConfigEntry) -> dict[str, Any]:
        """Keep saved or registered identity ahead of a live charger's report."""
        data = dict(entry.data)
        serial = async_get_known_serial(self.hass, entry)
        if not serial and (runtime := getattr(entry, "runtime_data", None)):
            serial = runtime.client.state.info.serial
        if serial:
            data[CONF_SERIAL] = serial
        return data

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer an explicit connection choice for the existing charger."""
        entry = self._get_reconfigure_entry()
        self._connection = async_get_connection_state(self.hass, entry.entry_id)
        await self.async_set_unique_id(entry.unique_id or entry.data[CONF_ADDRESS])
        self._pending_data = self._entry_data(entry)
        self._pending_title = entry.title
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["lan", "use_bluetooth"]
        )

    async def async_step_lan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a LAN host and PIN before selecting LAN."""
        if user_input is not None:
            entry = self._current_entry()
            if entry and not self._pending_data.get(CONF_SERIAL):
                return self._lan_form({"base": "identity_unknown"})
            pin = user_input[CONF_PIN]
            if len(pin) != 6 or not (pin.isascii() and pin.isdecimal()):
                return self._lan_form({"base": "invalid_auth"})
            host = user_input[CONF_HOST].strip()
            if not host:
                return self._lan_form({"base": "cannot_connect"})
            if entry is None and host != self._pending_data.get(CONF_HOST):
                self._pending_data = {}
                self._pending_title = "Besen"
            self._pending_data.update({CONF_HOST: host, CONF_PIN: pin})
            self._operation_step = "lan"
            return await self._start_operation(TRANSPORT_LAN)
        return self._lan_form({})

    def _lan_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="lan",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST, default=self._pending_data.get(CONF_HOST, "")
                    ): str,
                    probatio.Required(
                        CONF_PIN, default=self._pending_data.get(CONF_PIN, DEFAULT_PIN)
                    ): PIN_SCHEMA,
                }
            ),
            errors=errors,
        )

    async def async_step_use_bluetooth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate Bluetooth before switching the saved connection."""
        if self._pending_data.get(CONF_ADDRESS, "").startswith("lan:"):
            return self.async_abort(reason="bluetooth_address_unknown")
        if user_input is not None:
            self._pending_data[CONF_PIN] = user_input[CONF_PIN]
            self._operation_step = "use_bluetooth"
            return await self._start_operation(TRANSPORT_BLUETOOTH)
        return self.async_show_form(step_id="use_bluetooth", data_schema=REAUTH_SCHEMA)

    async def _start_operation(self, transport: str) -> ConfigFlowResult:
        self._operation_error = None
        self._operation_task = self.hass.async_create_task(
            self._test_connection(transport),
            "Besen connection setup",
            eager_start=False,
        )
        return await self.async_step_connect()

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress while the charger sends verified status."""
        assert self._operation_task is not None
        if not self._operation_task.done():
            return self.async_show_progress(
                step_id="connect",
                progress_action="connecting",
                progress_task=self._operation_task,
            )
        try:
            self._operation_task.result()
        except asyncio.CancelledError:
            self._operation_error = "cannot_connect"
        except CannotConnect, CommandFailed, TimeoutError:
            self._operation_error = "cannot_connect"
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Unexpected Besen setup task error: %s", type(err).__name__)
            self._operation_error = "unknown"
        return self.async_show_progress_done(next_step_id="connection_done")

    async def _test_connection(self, transport: str) -> None:
        """Serialize validation, cleanup and restoration for an existing entry."""
        entry = self._current_entry()
        connection = async_get_connection_state(
            self.hass,
            entry.entry_id
            if entry
            else f"lan:{self._pending_data[CONF_HOST].casefold()}",
        )
        await self._async_use_connection(connection)
        async with connection.lock:
            await connection.async_cleanup()
            await self._test_connection_locked(transport, entry, connection)

    async def _test_connection_locked(
        self,
        transport: str,
        entry: BesenConfigEntry | None,
        connection: BesenConnectionState,
    ) -> None:
        """Release the old session, test the candidate and restore the old one.

        Saving and reloading happen only in the final flow step. Cancellation
        and failed validation leave the original entry and connection selected.
        """
        runtime = getattr(entry, "runtime_data", None) if entry else None
        candidate: BesenUdpClient | None = None
        stopped = False
        acquired_hub = False

        async def cleanup_candidate() -> None:
            nonlocal candidate, acquired_hub
            if candidate is not None:
                await candidate.async_stop()
                if candidate.is_connected:
                    raise CannotConnect("Test connection was not released")
                candidate = None
            if acquired_hub:
                acquired_hub = False
                await async_release_udp_hub(self.hass)

        try:
            if runtime:
                stopped = True
                await runtime.async_pause_connection()
            address = self._pending_data.get(CONF_ADDRESS, "lan:pending")
            if transport == TRANSPORT_LAN:
                hub = await async_acquire_udp_hub(self.hass)
                acquired_hub = True
                connection.async_set_cleanup(cleanup_candidate)
                candidate = BesenUdpClient(
                    address=address,
                    pin=self._pending_data[CONF_PIN],
                    hub=hub,
                    logger=_LOGGER,
                    host=self._pending_data[CONF_HOST],
                    serial=self._pending_data.get(CONF_SERIAL),
                    sync_clock=False,
                )
                await candidate.async_start()
                await candidate.async_wait_for_status(timeout=10)
                await candidate.async_wait_for_heartbeat()
                serial = candidate.state.info.serial
                if not serial:
                    self._operation_error = "cannot_connect"
                    return
                if (
                    expected_serial := self._pending_data.get(CONF_SERIAL)
                ) and serial != expected_serial:
                    self._operation_error = "wrong_device"
                    return
                if async_is_serial_configured(self.hass, serial, address=address):
                    self._operation_error = "already_configured"
                    return
                self._pending_data[CONF_HOST] = candidate.host
                self._pending_data[CONF_SERIAL] = serial
                if address == "lan:pending":
                    self._pending_data[CONF_ADDRESS] = f"lan:{serial}"
                    self._pending_title = candidate.state.info.model or "Besen"
                    self._pending_data[CONF_NAME] = self._pending_title
            else:
                _, serial = await _async_validate_input(
                    self.hass,
                    address=address,
                    pin=self._pending_data[CONF_PIN],
                    name=self._pending_data.get(CONF_NAME),
                    connection=connection,
                )
                if (expected_serial := self._pending_data.get(CONF_SERIAL)) and (
                    serial != expected_serial
                ):
                    self._operation_error = (
                        "wrong_device" if serial else "cannot_connect"
                    )
                    return
                if serial:
                    self._pending_data[CONF_SERIAL] = serial
            self._pending_data[CONF_TRANSPORT] = transport
        except _AlreadyConfigured:
            self._operation_error = "already_configured"
        except InvalidAuth:
            self._operation_error = "invalid_auth"
        except NoConnectablePath:
            self._operation_error = "no_connectable_path"
        except CannotConnect, CommandFailed, TimeoutError:
            self._operation_error = "cannot_connect"
        except Exception as err:  # noqa: BLE001
            # Exception messages can contain the PIN or charger address.
            _LOGGER.error(
                "Unexpected Besen connection setup error: %s", type(err).__name__
            )
            self._operation_error = "unknown"
        finally:
            try:
                await connection.async_cleanup()
            finally:
                if runtime and stopped:
                    assert entry is not None
                    if connection.cleanup_pending:
                        connection.restore_reload = (entry, runtime)
                        if self._removed:
                            self._async_schedule_restore_reload()
                    else:
                        await self._async_restore_connection(entry, runtime)

    async def _async_restore_connection(
        self, entry: BesenConfigEntry, runtime: BesenCoordinator
    ) -> None:
        """Retry interrupted restoration after the active flow has been removed."""
        connection = self._connection
        assert connection is not None
        try:
            await runtime.async_resume_connection()
        except asyncio.CancelledError:
            connection.restore_reload = (entry, runtime)
            raise
        except CannotConnect, InvalidAuth:
            connection.restore_reload = (entry, runtime)
        else:
            connection.restore_reload = None
        finally:
            if self._removed:
                self._async_schedule_restore_reload()

    async def async_step_connection_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Commit only verified connection data, preserving entry identity."""
        if self._operation_error == "already_configured":
            return self.async_abort(reason="already_configured")
        if self._operation_error:
            return self._connection_error_form({"base": self._operation_error})
        entry = self._current_entry()
        serial = self._pending_data.get(CONF_SERIAL)
        if serial and async_is_serial_configured(
            self.hass, serial, exclude_entry_id=entry.entry_id if entry else None
        ):
            return self.async_abort(reason="already_configured")
        if entry:
            assert self._connection is not None
            self._connection.restore_reload = None
            return self.async_update_reload_and_abort(
                entry,
                data=self._pending_data,
                reload_even_if_entry_is_unchanged=True,
            )
        assert serial is not None
        await self.async_set_unique_id(self._pending_data[CONF_ADDRESS])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._pending_title, data=self._pending_data
        )

    def _connection_error_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Return to the form that started connection validation."""
        if self._operation_step in ("reauth_confirm", "use_bluetooth"):
            return self.async_show_form(
                step_id=self._operation_step,
                data_schema=REAUTH_SCHEMA,
                errors=errors,
            )
        return self._lan_form(errors)

    @callback
    def _async_schedule_restore_reload(self) -> None:
        """Keep recovery pending until all successor connection flows have finished."""
        connection = self._connection
        if connection is None or (request := connection.restore_reload) is None:
            return
        entry, runtime = request

        @callback
        def reload_if_current() -> None:
            if connection.restore_reload is not request:
                return
            if (
                entry.state is not config_entries.ConfigEntryState.LOADED
                or getattr(entry, "runtime_data", None) is not runtime
            ):
                connection.restore_reload = None
                return
            if any(
                entry.async_get_active_flows(
                    self.hass,
                    {config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE},
                )
            ):
                return
            connection.restore_reload = None
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

        self.hass.loop.call_soon(reload_if_current)

    async def _async_cleanup_removed_flow(self) -> None:
        """Retry retained cleanup after cancelled validation has finished."""
        if self._operation_task is not None:
            await asyncio.gather(self._operation_task, return_exceptions=True)
        assert self._connection is not None
        async with self._connection.lock:
            try:
                await self._connection.async_cleanup()
            except CannotConnect:
                _LOGGER.warning("Besen setup cleanup still needs a retry")

    @callback
    @override
    def async_remove(self) -> None:
        """Cancel validation and restore the saved connection on cancellation."""
        self._removed = True
        if self._operation_task and not self._operation_task.done():
            self._operation_task.cancel()
        self._async_schedule_restore_reload()
        if self._connection is not None:
            self.hass.async_create_task(
                self._async_cleanup_removed_flow(),
                "Besen removed setup cleanup",
                eager_start=False,
            )
