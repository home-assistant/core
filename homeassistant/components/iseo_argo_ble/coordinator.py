"""Coordinator for the ISEO Argo BLE Lock integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bluetooth_data_tools import monotonic_time_coarse
from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key
from iseo_argo_ble import IseoAuthError, IseoClient, IseoConnectionError, LockState

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.core import HomeAssistant, callback

from .const import CONF_PRIV_SCALAR, DEFAULT_USER_SUBTYPE, STATE_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

type IseoConfigEntry = ConfigEntry[IseoCoordinator]


async def async_build_client(
    hass: HomeAssistant, data: Mapping[str, Any], ble_device: BLEDevice
) -> IseoClient:
    """Rebuild the Argo gateway client from a stored identity."""
    priv_int = int(data[CONF_PRIV_SCALAR], 16)
    priv = await hass.async_add_executor_job(derive_private_key, priv_int, SECP224R1())
    return IseoClient(
        address=data[CONF_ADDRESS],
        uuid_bytes=bytes.fromhex(data[CONF_UUID]),
        identity_priv=priv,
        subtype=DEFAULT_USER_SUBTYPE,
        ble_device=ble_device,
    )


class IseoCoordinator(ActiveBluetoothDataUpdateCoordinator[LockState | None]):
    """Poll an ISEO Argo lock whenever it advertises."""

    def __init__(
        self, hass: HomeAssistant, entry: IseoConfigEntry, client: IseoClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=entry.data[CONF_ADDRESS],
            mode=BluetoothScanningMode.PASSIVE,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_poll_lock,
            connectable=True,
        )
        self.config_entry = entry
        self.client = client
        # The lock accepts a single Bluetooth connection at a time, so polls and
        # commands have to take turns.
        self.connection_lock = asyncio.Lock()
        # None until the first reading tells us whether the lock has a door sensor.
        self.door_status_supported: bool | None = None

    @callback
    def _needs_poll(
        self,
        service_info: BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        """Return True when the lock is due for a fresh reading."""
        if self.connection_lock.locked():
            return False
        if self.door_status_supported is False:
            # This lock has no door sensor, so connecting would return nothing
            # new and would only cost battery; seeing it advertise is all the
            # reachability information there is.
            return False
        return (
            seconds_since_last_poll is None
            or seconds_since_last_poll >= STATE_POLL_INTERVAL.total_seconds()
        )

    async def _async_poll_lock(
        self, service_info: BluetoothServiceInfoBleak
    ) -> LockState:
        """Read the lock state over a Bluetooth connection."""
        async with self.connection_lock:
            self.client.update_ble_device(service_info.device)
            state = await self.client.read_state()
        self.door_status_supported = state.door_closed is not None
        return state

    @override
    async def _async_poll(self) -> None:
        """Poll the lock and log availability changes."""
        assert self._last_service_info

        try:
            self.data = await self._async_poll_data(self._last_service_info)
        except IseoAuthError as exc:
            if self.last_poll_successful:
                # A rejected identity never recovers on its own: the gateway has
                # to be enrolled on the lock again.
                _LOGGER.warning(
                    "%s rejected the Home Assistant identity (%s), delete the "
                    "integration and set it up again to enroll it anew",
                    self.name,
                    exc,
                )
                self.last_poll_successful = False
            return
        except (IseoConnectionError, BleakError, TimeoutError, OSError) as exc:
            if self.last_poll_successful:
                _LOGGER.info("%s is unavailable: %s", self.name, exc)
                self.last_poll_successful = False
            return
        except Exception:
            if self.last_poll_successful:
                _LOGGER.exception("%s: unexpected error while polling", self.name)
                self.last_poll_successful = False
            return
        finally:
            self._last_poll = monotonic_time_coarse()

        if not self.last_poll_successful:
            _LOGGER.info("%s is back online", self.name)
            self.last_poll_successful = True

        self._async_handle_bluetooth_poll()

    async def async_poll_now(self) -> bool:
        """Poll immediately instead of waiting for the next advertisement.

        Returns True when a fresh reading was applied.
        """
        if self._last_service_info is None:
            return False
        await self._async_poll()
        return self.last_poll_successful

    @callback
    @override
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Keep the client's Bluetooth device reference fresh."""
        self.client.update_ble_device(service_info.device)
        super()._async_handle_bluetooth_event(service_info, change)
