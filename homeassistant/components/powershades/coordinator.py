"""PowerShades data update coordinator."""

from dataclasses import dataclass, replace
from datetime import timedelta
import logging
import time

from pyowershades import (
    MODEL_NAMES,
    OP_GET_STATUS,
    OP_JOG_STOP,
    OP_SET_POSITION,
    PowerShadesConnection,
    PowerShadesTimeoutError,
    StatusReply,
    battery_percentage,
    build_set_position_payload,
    parse_status_reply,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# % The margin for considering the shade arrived at its target
POSITION_TOLERANCE = 2

# seconds before an unmoving target is changed from moving to still
STUCK_TIMEOUT = 15

PowerShadesConfigEntry = ConfigEntry["PowerShadesCoordinator"]


@dataclass(frozen=True)
class PowerShadesData:
    """State of one PowerShades device."""

    position: int | None = None
    battery_mv: int | None = None
    battery_percentage: int | None = None
    target_position: int | None = None


class PowerShadesCoordinator(DataUpdateCoordinator[PowerShadesData]):
    """Coordinator polling one PowerShades device and handling its pushes."""

    config_entry: PowerShadesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PowerShadesConfigEntry,
        connection: PowerShadesConnection,
    ) -> None:
        """Initialize the coordinator."""
        self.connection = connection
        self.ip_address: str = entry.data["ip"]
        self.entry_id = entry.entry_id
        self.serial_number = entry.data.get("serial")
        self.device_name = entry.data.get("name")
        self.mac_address: str | None = entry.data.get("mac")
        self.model: int | None = entry.data.get("model")
        self._target_position: int | None = None
        self._last_position: int | None = None
        self._last_change_time: float | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"PowerShades {self.ip_address}",
            update_interval=timedelta(seconds=10),
        )
        connection.set_status_callback(self._handle_status_push)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        name = (
            f"PowerShade {self.device_name}"
            if self.device_name
            else f"PowerShade {self.ip_address}"
        )
        identifiers = {(DOMAIN, self.entry_id)}
        if self.serial_number:
            identifiers.add((DOMAIN, str(self.serial_number)))
        model_name = (
            MODEL_NAMES.get(self.model, "Motorized Window Cover")
            if self.model is not None
            else "Motorized Window Cover"
        )
        return DeviceInfo(
            identifiers=identifiers,
            connections=(
                {(CONNECTION_NETWORK_MAC, self.mac_address)}
                if self.mac_address
                else set()
            ),
            name=name,
            manufacturer="PowerShades",
            model=model_name,
            serial_number=str(self.serial_number) if self.serial_number else None,
        )

    def _data_from_status(self, status: StatusReply) -> PowerShadesData:
        now = time.monotonic()
        position = status.position
        if position is not None:
            if (
                self._target_position is not None
                and abs(position - self._target_position) <= POSITION_TOLERANCE
            ):
                self._target_position = None
                self._last_change_time = None
            elif self._last_position is not None and position != self._last_position:
                moving_up = position > self._last_position
                if self._target_position is None or (
                    (self._target_position > self._last_position) != moving_up
                ):
                    # treat an unexpected direction change as externally-initiated move
                    self._target_position = 100 if moving_up else 0
                self._last_change_time = now
            elif (
                self._target_position is not None
                and self._last_change_time is not None
                and now - self._last_change_time >= STUCK_TIMEOUT
            ):
                self._target_position = None
                self._last_change_time = None
        self._last_position = position
        return PowerShadesData(
            position=position,
            battery_mv=status.battery_mv,
            battery_percentage=battery_percentage(status.battery_mv),
            target_position=self._target_position,
        )

    @callback
    def _handle_status_push(self, status: StatusReply) -> None:
        self.async_set_updated_data(self._data_from_status(status))

    async def _async_update_data(self) -> PowerShadesData:
        """Poll the device for status."""
        try:
            raw = await self.connection.async_request(OP_GET_STATUS)
        except PowerShadesTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_timeout",
                translation_placeholders={
                    "ip_address": self.ip_address,
                    "error": str(err),
                },
            ) from err
        status = parse_status_reply(raw)
        if status is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_malformed_reply",
                translation_placeholders={"ip_address": self.ip_address},
            )
        data = self._data_from_status(status)
        self.update_interval = timedelta(seconds=5 if data.position is None else 10)
        return data

    def _set_target(self, position: int | None) -> None:
        self._target_position = position
        self._last_change_time = time.monotonic() if position is not None else None
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, target_position=position))

    async def _async_command(self, op: int, payload: bytes = b"") -> None:
        try:
            await self.connection.async_request(op, payload)
        except PowerShadesTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_not_acknowledged",
                translation_placeholders={"ip_address": self.ip_address},
            ) from err

    async def async_set_position(self, position: int) -> None:
        """Move the shade to a position (0=closed, 100=open)."""
        self._set_target(position)
        try:
            await self._async_command(
                OP_SET_POSITION, build_set_position_payload(position)
            )
        except HomeAssistantError:
            self._set_target(None)
            raise
        await self.async_request_refresh()

    async def async_stop(self) -> None:
        """Stop shade movement."""
        self._set_target(None)
        await self._async_command(OP_JOG_STOP)
        await self.async_request_refresh()
