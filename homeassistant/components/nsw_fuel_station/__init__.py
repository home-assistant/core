"""The nsw_fuel_station component."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import TYPE_CHECKING

from nsw_fuel import Station

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import NswFuelStationDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


SCAN_INTERVAL = datetime.timedelta(hours=1)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


class FuelCheckData:
    """Holds a global coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the data."""
        self.hass: HomeAssistant = hass
        self.coordinator: NswFuelStationDataUpdateCoordinator = (
            NswFuelStationDataUpdateCoordinator(
                hass,
            )
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NSW Fuel Station platform."""
    fuel_data = hass.data.setdefault(DOMAIN, {})
    if "coordinator" not in fuel_data:
        fuel_data["coordinator"] = FuelCheckData(hass).coordinator
    await fuel_data["coordinator"].async_config_entry_first_refresh()

    if "sensor" not in config:
        return True

    for platform_config in config["sensor"]:
        if platform_config["platform"] == DOMAIN:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=dict(platform_config),  # Convert to dict
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    fuel_data = hass.data.setdefault(DOMAIN, {})
    if "coordinator" not in fuel_data:
        fuel_data["coordinator"] = FuelCheckData(hass).coordinator
    await fuel_data["coordinator"].async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@dataclass
class StationPriceData:
    """Data structure for O(1) price and name lookups."""

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]
    fuel_types: dict[str, str]
