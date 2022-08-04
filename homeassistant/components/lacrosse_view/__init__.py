"""The LaCrosse View integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from lacrosse_view import HTTPError, LaCrosse, Location, LoginError, Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class LaCrosseCoordinatorData:
    """Data for the get_data function."""

    last_update: datetime
    api: LaCrosse


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LaCrosse View from a config entry."""

    async def get_data() -> list[Sensor]:
        """Get the data from the LaCrosse View."""
        now = datetime.utcnow()

        if data.last_update < now - timedelta(minutes=59):  # Get new token
            data.last_update = now
            try:
                await data.api.login(entry.data["username"], entry.data["password"])
            except LoginError as error:
                raise ConfigEntryAuthFailed from error

        # Get the timestamp for yesterday at 6 PM (this is what is used in the app, i noticed it when proxying the request)
        yesterday = now - timedelta(days=1)
        yesterday = yesterday.replace(hour=18, minute=0, second=0, microsecond=0)
        yesterday_timestamp = datetime.timestamp(yesterday)

        try:
            return await data.api.get_sensors(
                location=Location(id=entry.data["id"], name=entry.data["name"]),
                tz=hass.config.time_zone,
                start=str(int(yesterday_timestamp)),
                end=str(int(datetime.timestamp(now))),
            )
        except HTTPError as error:
            raise ConfigEntryNotReady from error

    api = LaCrosse(async_get_clientsession(hass))

    try:
        await api.login(entry.data["username"], entry.data["password"])
    except LoginError as error:
        raise ConfigEntryAuthFailed from error

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="LaCrosse View",
        update_method=get_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    data = LaCrosseCoordinatorData(last_update=datetime.utcnow(), api=api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
