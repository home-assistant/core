"""Hiportal implementation for home assistant."""
from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

class HiPortalAPIError(Exception):
    """Exception raised for unexpected responses from the HiPortal API."""


@dataclass
class SolarData:
    """Data model response from HiPortal API."""

    has_meter: bool
    to_grid_today: float
    from_grid_today: float
    to_grid_total: float
    from_grid_total: float
    pac: int
    e_today: float
    e_month: float
    e_total: float
    total_power: float
    time: str

class SolarWebSensor(CoordinatorEntity, SensorEntity):
    """Instance of sensors."""

    def __init__(self, coordinator, name, id, unit, icon, value_fn):
        """Initialize a new HiPortal sensor entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._value_fn = value_fn
        self._attr_unique_id =  id
        self._attr_has_entity_name = True
        self.icon=icon

    @property
    def native_value(self):
        """Return the native measurement."""
        return self._value_fn(self.coordinator.data)

async def poll_for_data(session, login_info):
    """Fetch data from the HiPortal API.

    If the response type is HTML, the session is not authenticated, so we perform a login.
    After successful authentication, the session uses a cookie to fetch the solar data.
    """
    url = "https://www.hyponportal.com/pilotview/countGeneration"
    login_url = "https://www.hyponportal.com/signin"
    headers = { "User-Agent": "Mozilla/5" }

    async with session.get(url, headers=headers) as resp:
        if "application/json" in resp.headers.get("Content-Type", ""):
            parsed = await resp.json()
            raw_data = parsed["data"]

            return await _convert_api_repsonse(raw_data)

        if "text/html" in resp.headers.get("Content-Type", ""):
            # Login
            async with session.post(login_url, json=login_info, headers=headers) as login_resp:
                if login_resp.status != 200:
                    raise HiPortalAPIError("Login failed")
            # Retry
            async with session.get(url, headers=headers) as retry_resp:
                parsed = await retry_resp.json()
                raw_data = parsed["data"]

                return await _convert_api_repsonse(raw_data)
        else:
            raise HiPortalAPIError("Unexpected content type")

async def async_setup_entry(hass, config, async_add_entities):
    """Set up login information and initialize the coordinator."""
    session = aiohttp.ClientSession()

    username = config.data[CONF_USERNAME]
    password = config.data[CONF_PASSWORD]

    login_info = {
        "account": username,
        "password": password,
        "rememberMe": True
    }

    async def async_update_data():
        return await poll_for_data(session, login_info)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="solar_data",
        update_method=async_update_data,
        update_interval=timedelta(minutes=2),
    )

    # Initial fetch
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        SolarWebSensor(coordinator, "Current Power", "current_power", UnitOfPower.WATT, "mdi:solar-power", lambda d: d.pac),
        SolarWebSensor(coordinator, "Daily Yield", "daily_yield", UnitOfEnergy.KILO_WATT_HOUR, "mdi:sun-angle", lambda d: d.e_today),
        SolarWebSensor(coordinator, "Monthly Yield", "monthly_yield", UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel", lambda d: d.e_month),
        SolarWebSensor(coordinator, "Total Yield", "total_yield", UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel-large", lambda d: d.e_total),
    ]
    async_add_entities(sensors)

async def _convert_api_repsonse(raw_data):
    return SolarData(
                    has_meter=raw_data["hasMeter"],
                    to_grid_today=raw_data["toGridToday"],
                    from_grid_today=raw_data["fromGridToday"],
                    to_grid_total=raw_data["toGridTotal"],
                    from_grid_total=raw_data["fromGridTotal"],
                    pac=raw_data["pac"],
                    e_today=raw_data["eToday"],
                    e_month=raw_data["eMonth"],
                    e_total=raw_data["eTotal"],
                    total_power=raw_data["totalPower"],
                    time=raw_data["time"],
                )
