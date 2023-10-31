"""The SEMS Portal integration."""
from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
import re
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_EMAIL, CONF_POWERSTATIONID, CONF_TOKEN, DOMAIN, MANUFACTURER
from .sems_plantDetails import get_plantDetails
from .sems_powerflow import get_powerflow

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SEMS Portal from a config entry."""

    email: str = entry.data[CONF_EMAIL]
    token: str = entry.data[CONF_TOKEN]
    powerstationId: str = entry.data[CONF_POWERSTATIONID]
    websession = async_get_clientsession(hass)

    coordinator = SemsDataUpdateCoordinator(
        hass, websession, email, token, powerstationId, email
    )
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def extract_number(s):
    """Remove units from string and turn to number."""

    # Match one or more digits at the beginning of the string
    match = re.match(r"(\d+)", s)
    if match:
        return int(match.group(1))

    return None


class SemsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching AccuWeather data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        email: str,
        token: str,
        powerstationId: str,
        name: str,
    ) -> None:
        """Initialize."""
        self.session = session
        self.powerstationId = powerstationId
        self.token = token
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, email)},
            manufacturer=MANUFACTURER,
            name=name,
            configuration_url=("https://au.semsportal.com"),
        )

        update_interval = timedelta(seconds=20)
        _LOGGER.debug("Data will be update every %s", update_interval)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        data: dict[str, Any] = {}
        plant_information: Any = {}
        try:
            async with timeout(10):
                plant_information = await get_powerflow(
                    session=self.session,
                    power_station_id=self.powerstationId,
                    token=self.token,
                )

                plantDetails = await get_plantDetails(
                    session=self.session,
                    power_station_id=self.powerstationId,
                    token=self.token,
                )
        except (
            ClientResponseError,
            ClientError,
            Exception,
        ) as error:
            raise UpdateFailed(error) from error

        data = {
            "powerPlant": {
                "info": {
                    "name": plantDetails["info"]["stationname"],
                    "model": "GoodWe",
                    "powerstation_id": plantDetails["info"]["powerstation_id"],
                    "stationname": plantDetails["info"]["stationname"],
                    "battery_capacity": plantDetails["info"]["battery_capacity"],
                    "capacity": plantDetails["info"]["capacity"],
                    "monthGeneration": plantDetails["kpi"]["month_generation"],
                    "generationToday": plantDetails["kpi"]["power"],
                    "allTimeGeneration": plantDetails["kpi"]["total_power"],
                    "todayIncome": plantDetails["kpi"]["day_income"],
                    "totalIncome": plantDetails["kpi"]["total_income"],
                    "generationLive": extract_number(
                        plant_information["powerflow"]["pv"]
                    ),
                    "pvStatus": plant_information["powerflow"]["pvStatus"],
                    "battery": extract_number(
                        plant_information["powerflow"]["bettery"]
                    ),
                    "batteryStatus": plant_information["powerflow"]["betteryStatus"],
                    "batteryStatusStr": plant_information["powerflow"][
                        "betteryStatusStr"
                    ],
                    "houseLoad": extract_number(plant_information["powerflow"]["load"]),
                    "houseLoadStatus": plant_information["powerflow"]["loadStatus"],
                    "gridLoad": extract_number(plant_information["powerflow"]["grid"]),
                    "gridLoadStatus": plant_information["powerflow"]["gridStatus"],
                    "soc": plant_information["powerflow"]["soc"],
                    "socText": extract_number(
                        plant_information["powerflow"]["socText"]
                    ),
                },
                "inverters": [],
            }
        }

        return data
