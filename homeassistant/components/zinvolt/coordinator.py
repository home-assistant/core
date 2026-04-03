"""Coordinator for Zinvolt."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltError
from zinvolt.models import Battery, BatteryState, Unit, UnitType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ZinvoltConfigEntry = ConfigEntry[dict[str, ZinvoltDeviceCoordinator]]


@dataclass
class ZinvoltData:
    """Data for the Zinvolt integration."""

    battery: BatteryState
    batteries: dict[str, BatteryData]


@dataclass
class BatteryData:
    """Data per battery unit."""

    sw_version: str
    model: str
    points: dict[str, bool]


class ZinvoltDeviceCoordinator(DataUpdateCoordinator[ZinvoltData]):
    """Class for Zinvolt devices."""

    battery_units: dict[str, Unit]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ZinvoltConfigEntry,
        client: ZinvoltClient,
        battery: Battery,
    ) -> None:
        """Initialize the Zinvolt device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Zinvolt {battery.identifier}",
            update_interval=timedelta(minutes=5),
        )
        self.battery = battery
        self.client = client

    async def _async_setup(self) -> None:
        """Set up the Zinvolt integration."""
        try:
            units = await self.client.get_units(self.battery.identifier)
        except ZinvoltError as err:
            raise UpdateFailed(
                translation_key="update_failed", translation_domain=DOMAIN
            ) from err
        self.battery_units = {
            unit.serial_number: unit for unit in units if unit.type is UnitType.BATTERY
        }

    async def _async_update_data(self) -> ZinvoltData:
        """Update data from Zinvolt."""
        try:
            battery_state = await self.client.get_battery_status(
                self.battery.identifier
            )
            battery_units = {
                unit_serial_number: await self.client.get_battery_unit(
                    self.battery.identifier, unit_serial_number
                )
                for unit_serial_number in self.battery_units
            }
        except ZinvoltError as err:
            raise UpdateFailed(
                translation_key="update_failed",
                translation_domain=DOMAIN,
            ) from err
        return ZinvoltData(
            battery_state,
            {
                serial_number: BatteryData(
                    battery_unit.version.current_version,
                    battery_unit.battery_model,
                    {
                        point.point.lower(): point.normal
                        for point in battery_unit.points
                    },
                )
                for serial_number, battery_unit in battery_units.items()
            },
        )
