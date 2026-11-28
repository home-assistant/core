"""Data update coordinator for E3/DC devices."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from e3dc_ess_modbus import E3dcPowerStation, NotAnE3dcError, PowerMeterType
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN, SCAN_INTERVAL, PartKind

_LOGGER = logging.getLogger(__name__)

# The components the entities read. The poll skips those the firmware doesn't serve.
POLLED_COMPONENTS = (
    "power",
    "battery_limits",
    "wide_power_meters",
    "power_meters",
    "inverter_mode_control",
    "grid_control",
    "inverters",
)
# The components that tell which optional hardware is installed, read once
HARDWARE_COMPONENTS = ("wallboxes",)


@dataclass(frozen=True, kw_only=True, order=True)
class E3dcPart:
    """A power meter or inverter of the power station, with its own device."""

    kind: PartKind
    slot: int  # E3/DC counts the slots from 0

    @property
    def number(self) -> int:
        """The part's number, counted from 1."""
        return self.slot + 1

    @property
    def built_in(self) -> bool:
        """Whether this is the power station's own inverter."""
        return self.kind is PartKind.INVERTER and self.slot == 0


def _installed_meters(device: E3dcPowerStation) -> list[int]:
    """The power meter slots with a meter configured, other than the grid connection point.

    The power station's own sensors cover the meter at the grid connection point.
    """
    return [
        number
        for number, meter in device.power_meter_readings.items()
        if meter.is_installed and meter.meter_type is not PowerMeterType.ROOT
    ]


def _connected_inverters(device: E3dcPowerStation) -> list[int]:
    """The power station's own inverter, and each additional one on the grid."""
    return [
        number
        for number, inverter in (device.inverters or {}).items()
        if number == 0 or inverter.is_connected
    ]


PART_SLOTS: dict[PartKind, Callable[[E3dcPowerStation], Iterable[int]]] = {
    PartKind.POWER_METER: _installed_meters,
    PartKind.INVERTER: _connected_inverters,
}

type E3dcConfigEntry = ConfigEntry[E3dcDataUpdateCoordinator]


class E3dcDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Poll the power station."""

    config_entry: E3dcConfigEntry
    station_device_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: E3dcConfigEntry,
        device: E3dcPowerStation,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device
        # The parts the power station reported in the last successful poll
        self.parts: set[E3dcPart] = set()

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        identity = self.device.identity
        serial = self.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        return dr.DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=identity.manufacturer or DEFAULT_NAME,
            model=identity.model or None,
            serial_number=identity.serial_number or None,
            sw_version=identity.firmware_release or None,
        )

    @override
    async def _async_setup(self) -> None:
        # The first poll also reads the identity and probes which blocks the station serves
        await self._async_poll(HARDWARE_COMPONENTS)
        if self.device.serial_number != self.config_entry.unique_id:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="serial_mismatch",
                translation_placeholders={
                    "expected": str(self.config_entry.unique_id),
                    "found": str(self.device.serial_number),
                },
            )
        # Register the power station before its parts, which link to it
        station = dr.async_get(self.hass).async_get_or_create_from_info(
            config_entry_id=self.config_entry.entry_id, device_info=self.device_info
        )
        self.station_device_id = station.id

    @override
    async def _async_update_data(self) -> None:
        await self._async_poll(POLLED_COMPONENTS)
        self.parts = {
            E3dcPart(kind=kind, slot=slot)
            for kind, slots_fn in PART_SLOTS.items()
            for slot in slots_fn(self.device)
        }

    async def _async_poll(self, components: tuple[str, ...]) -> None:
        """Read the components from the power station, or raise."""
        try:
            report = await self.device.async_poll(components)
        except NotAnE3dcError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="not_e3dc",
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if report.failed:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from ExceptionGroup(
                "components failed to refresh", list(report.failed.values())
            )
