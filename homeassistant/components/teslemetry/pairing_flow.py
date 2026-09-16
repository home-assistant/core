"""Shared Bluetooth pairing steps for the Teslemetry integration.

The vehicle subentry flow and the rejected-key repair flow run the same
find-and-pair steps but produce different flow results, so the shared base
lives here rather than in either flow's own module.
"""

from abc import ABC, abstractmethod
import asyncio
from typing import TYPE_CHECKING, Any, override

from bleak.exc import BleakError
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    NotOnWhitelistFault,
    TeslaFleetError,
    WhitelistOperationAttemptingToAddExistingKey,
)
from tesla_fleet_api.tesla.vehicle.bluetooth import VehicleBluetooth

from homeassistant.components.bluetooth import (
    async_discovered_service_info,
    async_request_active_scan,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult

from . import _BLE_KEY_ERRORS
from .const import LOGGER
from .helpers import async_get_ble_parent


class VehiclePairingFlow[_ResultT: FlowResult[Any, Any]](
    FlowHandler[Any, _ResultT, Any], ABC
):
    """Find a vehicle over Bluetooth and approve Home Assistant's virtual key on it."""

    def __init__(self) -> None:
        """Initialize the pairing state."""
        self._vin: str | None = None
        self._address: str | None = None
        self._vehicle: VehicleBluetooth | None = None
        self._pair_task: asyncio.Task[None] | None = None
        self._pair_error: dict[str, str] = {}

    @callback
    @abstractmethod
    def _async_finish_pairing(self) -> _ResultT:
        """Finish the flow once the virtual key is on the vehicle's whitelist."""

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> _ResultT:
        """Find the vehicle over Bluetooth and connect to it."""
        if TYPE_CHECKING:
            assert self._vin is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parent = await async_get_ble_parent(self.hass)
            except _BLE_KEY_ERRORS as err:
                LOGGER.debug("Bluetooth key load failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # The advertised BLE name is a hash of the VIN; match on its prefix.
                expected = parent.get_name(self._vin)[:17]
                device = None
                # The name is only in scan responses, so an active scan may be needed to see it.
                await async_request_active_scan(self.hass)
                for info in async_discovered_service_info(self.hass, connectable=True):
                    if info.name and info.name.startswith(expected):
                        device = info.device
                        self._address = info.address
                        break

                if device is None:
                    errors["base"] = "device_not_found"
                else:
                    # Uses default keepalive so the link survives the on-screen key-approval wait.
                    self._vehicle = parent.vehicles.createBluetooth(
                        self._vin, device=device
                    )
                    try:
                        await self._vehicle.connect()
                    except (BleakError, TeslaFleetError, TimeoutError) as err:
                        LOGGER.error("Failed to connect over Bluetooth: %s", err)
                        await self._async_disconnect()
                        errors["base"] = "cannot_connect"
                    else:
                        return await self.async_step_pair()

        return self.async_show_form(
            step_id="scan",
            errors=errors,
            description_placeholders={"vin": self._vin},
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> _ResultT:
        """Check whether the virtual key is already whitelisted on the vehicle."""
        if TYPE_CHECKING:
            assert self._vehicle is not None
        try:
            await self._vehicle.handshakeVehicleSecurity()
        except NotOnWhitelistFault:
            return await self.async_step_instructions()
        except (BleakError, TeslaFleetError, TimeoutError) as err:
            LOGGER.error("Bluetooth security handshake failed: %s", err)
            await self._async_disconnect()
            # The scan step owns the form; re-show it so a retry redoes scan and connect.
            return self.async_show_form(
                step_id="scan",
                errors={"base": "cannot_connect"},
                description_placeholders={"vin": self._vin or ""},
            )
        await self._async_disconnect()
        return self._async_finish_pairing()

    async def async_step_instructions(
        self, user_input: dict[str, Any] | None = None
    ) -> _ResultT:
        """Ask the user to approve the virtual key on the vehicle touchscreen."""
        if user_input is not None:
            return await self.async_step_authorize()
        errors = self._pair_error
        self._pair_error = {}
        return self.async_show_form(
            step_id="instructions",
            errors=errors,
            description_placeholders={"vin": self._vin or ""},
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> _ResultT:
        """Add the virtual key to the vehicle while showing pairing progress."""
        if self._pair_task is None:
            if TYPE_CHECKING:
                assert self._vehicle is not None
            # pair() can take minutes, so run it as a progress task rather than blocking the flow.
            self._pair_task = self.hass.async_create_task(self._vehicle.pair())

        if not self._pair_task.done():
            return self.async_show_progress(
                step_id="authorize",
                progress_action="pair",
                progress_task=self._pair_task,
                description_placeholders={"vin": self._vin or ""},
            )

        task = self._pair_task
        self._pair_task = None
        try:
            task.result()
        except (BluetoothTransportError, BleakError) as err:
            LOGGER.debug("Bluetooth transport failed during pairing: %s", err)
            self._pair_error = {"base": "cannot_connect"}
            return self.async_show_progress_done(next_step_id="instructions")
        except (BluetoothTimeout, TimeoutError) as err:
            LOGGER.debug("Bluetooth pairing timed out: %s", err)
            self._pair_error = {"base": "timeout"}
            return self.async_show_progress_done(next_step_id="instructions")
        except WhitelistOperationAttemptingToAddExistingKey as err:
            LOGGER.debug("Virtual key is already on the whitelist: %s", err)
        except TeslaFleetError as err:
            LOGGER.error("Bluetooth pairing was rejected: %s", err)
            self._pair_error = {"base": "pair_failed"}
            return self.async_show_progress_done(next_step_id="instructions")
        except Exception:
            # async_remove() only runs if the flow is still tracked when this step raises.
            await self._async_disconnect()
            raise
        return self.async_show_progress_done(next_step_id="pair")

    async def _async_disconnect(self) -> None:
        """Disconnect the BLE link, if any, and drop the reference to it."""
        vehicle = self._vehicle
        if vehicle is not None:
            try:
                await vehicle.disconnect()
            except (BleakError, TeslaFleetError, TimeoutError) as err:
                LOGGER.debug("Error disconnecting Bluetooth: %s", err)
            finally:
                self._vehicle = None

    @callback
    @override
    def async_remove(self) -> None:
        """Release resources if the flow is abandoned mid-pairing."""
        if self._pair_task is not None and not self._pair_task.done():
            self._pair_task.cancel()
        if self._vehicle is not None:
            self.hass.async_create_task(self._async_disconnect())
