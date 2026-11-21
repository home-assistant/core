"""Data update coordinator for the Tridonic DALI integration."""

import asyncio
from dataclasses import dataclass, replace
from datetime import timedelta
import logging
from typing import override

from dali.address import GearShort
from dali.driver.serial import DriverLubaRs232
from dali.exceptions import DALISequenceError, TransmissionError
from dali.gear.general import (
    QueryActualLevel,
    QueryControlGearPresent,
    QueryMaxLevel,
    QueryMinLevel,
)
from dali.gear.led import QueryDimmingCurve
from dali.sequences import QueryDeviceTypes

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_TYPE_LED,
    DOMAIN,
    GEAR_DEVICE_TYPE_NAMES,
    SUPPORTED_GEAR_DEVICE_TYPES,
    registry_identifier,
)

type DaliConfigEntry = ConfigEntry[DaliCoordinator]

SCAN_INTERVAL = timedelta(seconds=30)
FULL_SCAN_INTERVAL = timedelta(minutes=5)
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DaliDeviceData:
    """Identification data shared by DALI gears and input devices."""

    gtin: int | None = None
    identification_number: int | None = None
    serial_no: str | None = None
    batch_no: str | None = None
    firmware_version: str | None = None
    hardware_version: str | None = None
    # Number of the highest memory bank the unit implements. Banks need not be
    # contiguous, so this only rules bank reads out, never in.
    last_memory_bank: int | None = None


@dataclass(frozen=True, slots=True)
class DaliGearData(DaliDeviceData):
    """State and identification data for one DALI control gear."""

    level: int | None = None
    min_level: int = 1
    max_level: int | None = None
    linear_dimming: bool = False
    device_types: tuple[int, ...] = ()


class DaliCoordinator(DataUpdateCoordinator[dict[int, DaliGearData]]):
    """Coordinate DALI gear discovery and state updates."""

    config_entry: DaliConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        driver: DriverLubaRs232,
        config_entry: DaliConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.driver = driver
        self._last_full_scan: float | None = None
        # Serialises the periodic bus scan with single-gear command updates so a
        # mid-scan read cannot publish a stale level over a just-sent command.
        self._refresh_lock = asyncio.Lock()
        # Control gear ever seen, to tell a first discovery from a recovery.
        self._seen_gear: set[int] = set()

    async def async_update_gear(
        self, address: int, optimistic_level: int | None = None
    ) -> None:
        """Refresh a single gear and notify entities, without a full bus scan.

        ``optimistic_level`` overrides the queried brightness with the value a
        just-sent level settles to. A DALI gear reaches a commanded level over
        its configured fade time, so an immediate ``QueryActualLevel`` reads a
        mid-fade value; the override shows the target at once and the periodic
        scan reconciles it.
        """
        async with self._refresh_lock:
            gear = await self._query_gear(address)
            data = dict(self.data or {})
            if gear is None:
                data.pop(address, None)
            elif optimistic_level is not None:
                data[address] = replace(gear, level=optimistic_level)
            else:
                data[address] = gear
            self._log_availability_transitions(data)
            # Publish without async_set_updated_data so frequent commands to one
            # gear cannot keep rescheduling the periodic scan and starve the
            # discovery of other gear.
            self.data = data
            self.async_update_listeners()

    def _log_availability_transitions(self, new_data: dict[int, DaliGearData]) -> None:
        """Log control gear becoming unavailable or recovering, once each.

        The coordinator update succeeds even when a gear stops responding, so
        its built-in failure logging never reports these outages. A gear is only
        "recovered" once it has been seen before; its first appearance is a plain
        discovery.
        """
        previous = set(self.data or {})
        current = set(new_data)
        for address in previous - current:
            LOGGER.info("DALI control gear %d stopped responding", address)
        for address in current - previous:
            if address in self._seen_gear:
                LOGGER.info("DALI control gear %d is responding again", address)
        self._seen_gear |= current

    async def _query_gear(self, address: int) -> DaliGearData | None:
        """Return a gear's state and metadata, or None when absent.

        A known gear is queried again after a miss so a single dropped DALI
        response does not flip a light to unavailable.
        """
        gear = await self._query_gear_once(address)
        if gear is None and self.data and address in self.data:
            gear = await self._query_gear_once(address)
        return gear

    async def _query_gear_once(self, address: int) -> DaliGearData | None:
        """Return a gear's state and metadata, or None when absent."""
        gear_address = GearShort(address)
        try:
            present = await self.driver.send(QueryControlGearPresent(gear_address))
            if present is None or not present.value:
                return None
            # A framing error means several gear answered at once: the address
            # collides and cannot be queried individually, so treat the gear as
            # unavailable and leave the collision to the dedicated repair.
            if present.raw_value is not None and present.raw_value.error:
                return None
            # Device types are a static property of the gear, so a known gear
            # reuses the value from the last scan instead of re-querying it on
            # every single-gear refresh after a command.
            cached = self.data.get(address) if self.data else None
            if cached is not None:
                device_types = cached.device_types
            else:
                device_types = tuple(
                    device_type
                    for device_type in await self.driver.send(
                        QueryDeviceTypes(gear_address)
                    )
                    if device_type in SUPPORTED_GEAR_DEVICE_TYPES
                )
            if not device_types:
                return None
            level = await self.driver.send(QueryActualLevel(gear_address))
            min_level = _response_value(
                await self.driver.send(QueryMinLevel(gear_address))
            )
            if min_level is None or not 1 <= min_level <= 254:
                # A dropped minimum-level reply would otherwise reset a known
                # minimum to 1 and skew the conversion; keep the cached minimum
                # for gear already seen, defaulting only for newly found gear.
                min_level = cached.min_level if cached is not None else 1
            max_level = _response_value(
                await self.driver.send(QueryMaxLevel(gear_address))
            )
            if max_level is None or not 1 <= max_level <= 254:
                # A dropped or out-of-range maximum-level reply would otherwise
                # clear a known maximum and lift the command clamp to full power;
                # keep the cached maximum for gear already seen, defaulting to no
                # cap only for newly found gear.
                max_level = cached.max_level if cached is not None else None
            linear_dimming = False
            if DEVICE_TYPE_LED in device_types:
                curve = await self.driver.send(QueryDimmingCurve(gear_address))
                if curve is None or curve.raw_value is None or curve.raw_value.error:
                    # A dropped or framing-error dimming-curve reply would
                    # otherwise default to, or wrongly decode as, the logarithmic
                    # curve and flip a linear gear's brightness; treat it as a
                    # miss so the known-gear retry re-reads it.
                    return None
                linear_dimming = curve.raw_value.as_integer == 1
        except (OSError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        except DALISequenceError, TransmissionError:
            # A sequence error, or the interface rejecting a frame for this one
            # gear (a collision, arbitration loss, or the bus sagging under the
            # extra frames a multi-type gear needs), means this address cannot be
            # queried this round. Treat it as a miss so one noisy gear cannot
            # abort discovery of the rest of the bus; a genuinely bus-wide fault
            # surfaces instead as every gear missing, taking the lights
            # unavailable anyway.
            return None

        return DaliGearData(
            level=_dali_level_to_brightness(_response_value(level), linear_dimming),
            min_level=min_level,
            max_level=max_level,
            linear_dimming=linear_dimming,
            device_types=device_types,
        )

    @override
    async def _async_update_data(self) -> dict[int, DaliGearData]:
        """Refresh known gear, scanning the whole bus periodically.

        Every cycle re-queries the gear already known so lights track external
        changes, but the full 64-address scan only runs every
        ``FULL_SCAN_INTERVAL`` to keep bus traffic low.
        """
        if not self.driver.is_connected:
            # The interface is gone, typically unplugged. Reloading opens the
            # serial port again and rescans the bus; while the interface stays
            # away the entry retries in the background instead, and a replug is
            # picked up straight away by USB discovery.
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_lost",
            )
        now = self.hass.loop.time()
        full_scan = (
            self._last_full_scan is None
            or now - self._last_full_scan >= FULL_SCAN_INTERVAL.total_seconds()
        )
        addresses = range(64) if full_scan else tuple(self.data or ())
        if full_scan:
            LOGGER.info("Scanning DALI bus for control gear")
        data: dict[int, DaliGearData] = {}
        async with self._refresh_lock:
            for address in addresses:
                gear = await self._query_gear(address)
                if gear is not None:
                    data[address] = gear
        if full_scan:
            LOGGER.info("Found %d control gear", len(data))
            self._last_full_scan = now
        self._log_availability_transitions(data)
        return data

    def close(self) -> None:
        """Close the serial transport."""
        if transport := getattr(self.driver, "_transport", None):
            transport.close()

    def device_data(self, address: int) -> DaliDeviceData:
        """Return the memory bank 0 data held for a gear."""
        data = self.data.get(address)
        return data if data is not None else DaliDeviceData()

    def device_info(self, entry_id: str, title: str, address: int) -> DeviceInfo:
        """Return device information for a DALI gear."""
        data = self.device_data(address)
        model = _gear_model(data.device_types if isinstance(data, DaliGearData) else ())
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    registry_identifier(entry_id, address, input_device=False),
                )
            },
            name=f"{self._interface_label(title)}/{address} (gear)",
            model=f"{model} (address {address})",
            model_id=str(data.gtin) if data.gtin is not None else None,
            serial_number=data.serial_no,
            sw_version=data.firmware_version,
            hw_version=data.hardware_version,
        )

    def hub_device_info(self, entry_id: str, title: str) -> DeviceInfo:
        """Return device information for the DALI interface itself."""
        return DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=self._interface_label(title),
            manufacturer="Lunatone",
            model="USB-DALI2 interface",
        )

    def _interface_label(self, title: str) -> str:
        """Return a short interface label from the entry's USB identity.

        The config-entry title is the full human-readable serial-port string,
        which is too long for a device name. The USB unique ID is a structured
        ``vid:pid_serial_manufacturer_description`` field, so a compact
        ``model_serial`` label is derived from it, falling back to the title
        for non-USB interfaces that have no unique ID.
        """
        unique_id = self.config_entry.unique_id
        if unique_id:
            parts = unique_id.split("_", 3)
            if len(parts) == 4:
                _vid_pid, serial, _manufacturer, description = parts
                if serial:
                    model = description.replace(" ", "_")
                    return f"{model}_{serial}" if model else serial
        return title


def _gear_model(device_types: tuple[int, ...]) -> str:
    """Return a model string naming a control gear's device-type parts."""
    if not device_types:
        return "DALI control gear"
    labels = [_gear_type_label(device_type) for device_type in device_types]
    return "DALI control gear – " + ", ".join(labels)


def _gear_type_label(device_type: int) -> str:
    """Return a label for one control-gear device type and its IEC part."""
    name = GEAR_DEVICE_TYPE_NAMES.get(device_type, f"Device type {device_type}")
    return f"{name} (DT{device_type}, IEC 62386-{201 + device_type})"


def _dali_level_to_brightness(level: object, linear_dimming: bool) -> int | None:
    """Convert a DALI arc-power level to Home Assistant brightness.

    The curve depends only on the level and dimming type (IEC 62386-207); the
    configured minimum level clamps commands, it does not rescale the readback.
    """
    if not isinstance(level, int) or level >= 255:
        return None
    if level <= 0:
        return 0
    if level >= 254:
        return 255
    if linear_dimming:
        return round(1 + (level - 1) * 254 / 253)
    return max(1, round(255 * 10 ** (((level - 254) * 3) / 253)))


def _brightness_to_dali_level(
    brightness: int, linear_dimming: bool, min_level: int
) -> int:
    """Convert Home Assistant brightness (1-255) to a DALI arc-power level.

    The DALI level axis is coarser than the 1-255 brightness axis, so rounding
    each direction independently makes a set level read back as a different
    brightness and the UI slider jumps. The lowest level whose readback is
    closest to the request is chosen instead, making the mapping a stable right
    inverse of the readback: every reported brightness maps back to the level it
    came from, regardless of the gear's minimum level.
    """
    return min(
        range(min_level, 255),
        key=lambda level: (
            abs((_dali_level_to_brightness(level, linear_dimming) or 0) - brightness),
            level,
        ),
    )


def _response_value(response: object) -> int | None:
    """Return a numeric response value."""
    value = getattr(response, "value", None)
    return value if isinstance(value, int) else None
