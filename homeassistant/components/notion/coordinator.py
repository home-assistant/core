"""Define a Notion data coordinator."""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from aionotion.bridge.models import Bridge
from aionotion.client import Client
from aionotion.errors import InvalidCredentialsError, NotionError
from aionotion.listener.models import Listener
from aionotion.sensor.models import Sensor
from aionotion.user.models import UserPreferences

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

DATA_BRIDGES = "bridges"
DATA_LISTENERS = "listeners"
DATA_SENSORS = "sensors"
DATA_USER_PREFERENCES = "user_preferences"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)


@callback
def _async_register_new_bridge(
    hass: HomeAssistant, entry: ConfigEntry, bridge: Bridge
) -> None:
    """Register a new bridge."""
    if name := bridge.name:
        bridge_name = name.capitalize()
    else:
        bridge_name = str(bridge.id)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, bridge.hardware_id)},
        manufacturer="Silicon Labs",
        model=str(bridge.hardware_revision),
        name=bridge_name,
        sw_version=bridge.firmware_version.wifi,
    )


@dataclass
class NotionData:
    """Define a manager class for Notion data."""

    hass: HomeAssistant
    entry: ConfigEntry

    # Define a dict of bridges, indexed by bridge ID (an integer):
    bridges: dict[int, Bridge] = field(default_factory=dict)

    # Define a dict of listeners, indexed by listener UUID (a string):
    listeners: dict[str, Listener] = field(default_factory=dict)

    # Define a dict of sensors, indexed by sensor UUID (a string):
    sensors: dict[str, Sensor] = field(default_factory=dict)

    # Define a user preferences response object:
    user_preferences: UserPreferences | None = field(default=None)

    def update_bridges(self, bridges: list[Bridge]) -> None:
        """Update the bridges."""
        for bridge in bridges:
            # If a new bridge is discovered, register it:
            if bridge.id not in self.bridges:
                _async_register_new_bridge(self.hass, self.entry, bridge)
            self.bridges[bridge.id] = bridge

    def update_listeners(self, listeners: list[Listener]) -> None:
        """Update the listeners."""
        self.listeners = {listener.id: listener for listener in listeners}

    def update_sensors(self, sensors: list[Sensor]) -> None:
        """Update the sensors."""
        self.sensors = {sensor.uuid: sensor for sensor in sensors}

    def update_user_preferences(self, user_preferences: UserPreferences) -> None:
        """Update the user preferences."""
        self.user_preferences = user_preferences

    def asdict(self) -> dict[str, Any]:
        """Represent this dataclass (and its Pydantic contents) as a dict."""
        data: dict[str, Any] = {
            DATA_BRIDGES: [item.to_dict() for item in self.bridges.values()],
            DATA_LISTENERS: [item.to_dict() for item in self.listeners.values()],
            DATA_SENSORS: [item.to_dict() for item in self.sensors.values()],
        }
        if self.user_preferences:
            data[DATA_USER_PREFERENCES] = self.user_preferences.to_dict()
        return data


class NotionDataUpdateCoordinator(DataUpdateCoordinator[NotionData]):
    """Define a Notion data coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        client: Client,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=entry.data[CONF_USERNAME],
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self._client = client
        self._entry = entry

    async def _async_update_data(self) -> NotionData:
        """Fetch data from Notion."""
        data = NotionData(hass=self.hass, entry=self._entry)

        try:
            async with asyncio.TaskGroup() as tg:
                bridges = tg.create_task(self._client.bridge.async_all())
                listeners = tg.create_task(self._client.listener.async_all())
                sensors = tg.create_task(self._client.sensor.async_all())
                user_preferences = tg.create_task(self._client.user.async_preferences())
        except BaseExceptionGroup as err:
            result = err.exceptions[0]
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed(
                    "Invalid username and/or password"
                ) from result
            if isinstance(result, NotionError):
                raise UpdateFailed(
                    f"There was a Notion error while updating: {result}"
                ) from result
            if isinstance(result, Exception):
                LOGGER.debug(
                    "There was an unknown error while updating: %s",
                    result,
                    exc_info=result,
                )
                raise UpdateFailed(
                    f"There was an unknown error while updating: {result}"
                ) from result
            if isinstance(result, BaseException):
                raise result from None

        data.update_bridges(bridges.result())
        data.update_listeners(listeners.result())
        data.update_sensors(sensors.result())
        data.update_user_preferences(user_preferences.result())

        return data
