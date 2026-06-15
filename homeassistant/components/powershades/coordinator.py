"""PowerShades data update coordinator."""

from dataclasses import dataclass, replace
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LIMIT_LOWER,
    LIMIT_UPPER,
    MODEL_NAMES,
    OP_CLEAR_LIMITS,
    OP_GET_SHADE_NAME,
    OP_GET_STATUS,
    OP_INDICATE,
    OP_JOG_DOWN,
    OP_JOG_STOP,
    OP_JOG_UP,
    OP_SET_LIMIT,
    OP_SET_POSITION,
    OP_STEP_DOWN,
    OP_STEP_UP,
)
from .protocol import (
    GET_SHADE_NAME_PAYLOAD,
    StatusReply,
    battery_percentage,
    build_set_limit_payload,
    build_set_name_payload,
    build_set_position_payload,
    parse_shade_name_reply,
    parse_status_reply,
)
from .udp import PowerShadesConnection, PowerShadesTimeoutError

_LOGGER = logging.getLogger(__name__)

# Within this distance of the target the shade counts as arrived
POSITION_TOLERANCE = 2

# How long the reported position can stay unchanged while heading to a
# target before the shade is considered stopped (e.g. by an external
# controller or a physical obstruction). Generous enough to absorb the
# motor ramp-up time and the gap before the first status push.
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
        if self.device_name:
            name = f"PowerShade {self.device_name}"
        else:
            name = f"PowerShade {self.ip_address}"

        # The entry_id is always present and never changes, so it's a
        # stable primary identifier. The serial is added once known so
        # devices set up before serials were stored (identified only by
        # entry_id) and devices set up after (identified only by serial)
        # converge onto the same device registry entry once both are
        # present - the registry merges identifier sets onto a matching
        # existing device rather than requiring an exact match.
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
                # Reached the target, whether it was set by Home Assistant
                # or inferred below from an externally-initiated move.
                self._target_position = None
                self._last_change_time = None
            elif self._last_position is not None and position != self._last_position:
                moving_up = position > self._last_position
                if self._target_position is None or (
                    (self._target_position > self._last_position) != moving_up
                ):
                    # No active target, or the shade just reversed
                    # direction (an external controller doesn't tell us
                    # its real target) - assume it's heading toward the
                    # natural limit in the observed direction.
                    self._target_position = 100 if moving_up else 0
                self._last_change_time = now
            elif (
                self._target_position is not None
                and self._last_change_time is not None
                and now - self._last_change_time >= STUCK_TIMEOUT
            ):
                # Position hasn't moved for a while even though we think
                # the shade is heading to a target - an external
                # controller or a physical obstruction stopped it. Stop
                # reporting opening/closing.
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
        """Handle a status packet (runs on the event loop)."""
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
        # Poll faster while the position is unknown
        self.update_interval = timedelta(seconds=5 if data.position is None else 10)
        return data

    def _set_target(self, position: int | None) -> None:
        """Update the movement target and notify entities immediately."""
        self._target_position = position
        self._last_change_time = time.monotonic() if position is not None else None
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, target_position=position))

    async def _async_command(self, op: int, payload: bytes = b"") -> None:
        """Send a command and await the device's echo reply (ACK).

        Every command is acknowledged with a reply carrying the same op
        and sequence; the reply payload itself is meaningless (PoE
        shades may send a generic reply packet).
        """
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

    async def async_toggle(self) -> None:
        """Toggle the shade: stop if moving, otherwise open/close."""
        data = self.data
        if data is None or data.position is None:
            _LOGGER.warning("Cannot toggle shade %s: position unknown", self.ip_address)
            return
        if data.target_position is not None:
            await self.async_stop()
        elif data.position > 50:
            await self.async_set_position(0)
        else:
            await self.async_set_position(100)

    async def async_jog_up(self) -> None:
        """Jog the shade up until it reaches a limit or is stopped."""
        await self._async_command(OP_JOG_UP)
        await self.async_request_refresh()

    async def async_jog_down(self) -> None:
        """Jog the shade down until it reaches a limit or is stopped."""
        await self._async_command(OP_JOG_DOWN)
        await self.async_request_refresh()

    async def async_identify(self) -> None:
        """Make the shade motor indicate (wiggle) to identify it."""
        await self._async_command(OP_INDICATE)

    async def async_set_upper_limit(self) -> None:
        """Set the upper limit (fully open position)."""
        await self._async_command(OP_SET_LIMIT, build_set_limit_payload(LIMIT_UPPER))
        _LOGGER.info("Set upper limit for %s", self.ip_address)

    async def async_set_lower_limit(self) -> None:
        """Set the lower limit (fully closed position)."""
        await self._async_command(OP_SET_LIMIT, build_set_limit_payload(LIMIT_LOWER))
        _LOGGER.info("Set lower limit for %s", self.ip_address)

    async def async_clear_limits(self) -> None:
        """Clear both limits."""
        await self._async_command(OP_CLEAR_LIMITS)
        _LOGGER.info("Cleared limits for %s", self.ip_address)

    async def async_step_up(self) -> None:
        """Move the motor up one step (for trimming limits)."""
        await self._async_command(OP_STEP_UP)

    async def async_step_down(self) -> None:
        """Move the motor down one step (for trimming limits)."""
        await self._async_command(OP_STEP_DOWN)

    async def async_set_shade_name(self, name: str) -> None:
        """Rename the shade on the device and sync the new name into HA."""
        await self._async_command(OP_GET_SHADE_NAME, build_set_name_payload(name))

        # Read the name back to confirm the device stored it
        try:
            reply = await self.connection.async_request(
                OP_GET_SHADE_NAME, GET_SHADE_NAME_PAYLOAD
            )
        except PowerShadesTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rename_not_confirmed",
                translation_placeholders={"ip_address": self.ip_address},
            ) from err
        confirmed = parse_shade_name_reply(reply)
        if not confirmed:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rename_empty_name",
                translation_placeholders={"ip_address": self.ip_address},
            )

        self.device_name = confirmed
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, "name": confirmed},
            title=f"PowerShade {confirmed}",
        )
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers=self.device_info["identifiers"]
        )
        if device is not None:
            device_registry.async_update_device(
                device.id, name=f"PowerShade {confirmed}"
            )
        _LOGGER.info("Renamed shade %s to %r", self.ip_address, confirmed)
