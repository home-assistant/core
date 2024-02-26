"""Support for Notion."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID

from aionotion import async_get_client
from aionotion.bridge.models import Bridge
from aionotion.errors import InvalidCredentialsError, NotionError
from aionotion.listener.models import Listener, ListenerKind
from aionotion.sensor.models import Sensor
from aionotion.user.models import UserPreferences

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    LOGGER,
    SENSOR_BATTERY,
    SENSOR_DOOR,
    SENSOR_GARAGE_DOOR,
    SENSOR_LEAK,
    SENSOR_MISSING,
    SENSOR_SAFE,
    SENSOR_SLIDING,
    SENSOR_SMOKE_CO,
    SENSOR_TEMPERATURE,
    SENSOR_WINDOW_HINGED,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

ATTR_SYSTEM_MODE = "system_mode"
ATTR_SYSTEM_NAME = "system_name"

DATA_BRIDGES = "bridges"
DATA_LISTENERS = "listeners"
DATA_SENSORS = "sensors"
DATA_USER_PREFERENCES = "user_preferences"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

# Define a map of old-API task types to new-API listener types:
TASK_TYPE_TO_LISTENER_MAP: dict[str, ListenerKind] = {
    SENSOR_BATTERY: ListenerKind.BATTERY,
    SENSOR_DOOR: ListenerKind.DOOR,
    SENSOR_GARAGE_DOOR: ListenerKind.GARAGE_DOOR,
    SENSOR_LEAK: ListenerKind.LEAK_STATUS,
    SENSOR_MISSING: ListenerKind.CONNECTED,
    SENSOR_SAFE: ListenerKind.SAFE,
    SENSOR_SLIDING: ListenerKind.SLIDING_DOOR_OR_WINDOW,
    SENSOR_SMOKE_CO: ListenerKind.SMOKE,
    SENSOR_TEMPERATURE: ListenerKind.TEMPERATURE,
    SENSOR_WINDOW_HINGED: ListenerKind.HINGED_WINDOW,
}


@callback
def is_uuid(value: str) -> bool:
    """Return whether a string is a valid UUID."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Notion as a config entry."""
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=session,
            use_legacy_auth=True,
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username and/or password") from err
    except NotionError as err:
        raise ConfigEntryNotReady("Config entry failed to load") from err

    async def async_update() -> NotionData:
        """Get the latest data from the Notion API."""
        data = NotionData(hass=hass, entry=entry)

        try:
            async with asyncio.TaskGroup() as tg:
                bridges = tg.create_task(client.bridge.async_all())
                listeners = tg.create_task(client.listener.async_all())
                sensors = tg.create_task(client.sensor.async_all())
                user_preferences = tg.create_task(client.user.async_preferences())
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

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.data[CONF_USERNAME],
        update_interval=DEFAULT_SCAN_INTERVAL,
        update_method=async_update,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    @callback
    def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
        """Migrate Notion entity entries.

        This migration focuses on unique IDs, which have changed because of a Notion API
        change:

        Old Format: <sensor_id>_<task_type>
        New Format: <listener_uuid>
        """
        if is_uuid(entry.unique_id):
            # If the unique ID is already a UUID, we don't need to migrate it:
            return None

        sensor_id_str, task_type = entry.unique_id.split("_", 1)
        sensor = next(
            sensor
            for sensor in coordinator.data.sensors.values()
            if sensor.id == int(sensor_id_str)
        )
        listener = next(
            listener
            for listener in coordinator.data.listeners.values()
            if listener.sensor_id == sensor.uuid
            and listener.definition_id == TASK_TYPE_TO_LISTENER_MAP[task_type].value
        )

        return {"new_unique_id": listener.id}

    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Notion config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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


class NotionEntity(CoordinatorEntity[DataUpdateCoordinator[NotionData]]):
    """Define a base Notion entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NotionData],
        listener_id: str,
        sensor_id: str,
        bridge_id: int,
        system_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        sensor = self.coordinator.data.sensors[sensor_id]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.hardware_id)},
            manufacturer="Silicon Labs",
            model=str(sensor.hardware_revision),
            name=str(sensor.name).capitalize(),
            sw_version=sensor.firmware_version,
        )

        if bridge := self._async_get_bridge(bridge_id):
            self._attr_device_info["via_device"] = (DOMAIN, bridge.hardware_id)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = listener_id
        self._bridge_id = bridge_id
        self._listener_id = listener_id
        self._sensor_id = sensor_id
        self._system_id = system_id
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._listener_id in self.coordinator.data.listeners
        )

    @property
    def listener(self) -> Listener:
        """Return the listener related to this entity."""
        return self.coordinator.data.listeners[self._listener_id]

    @callback
    def _async_get_bridge(self, bridge_id: int) -> Bridge | None:
        """Get a bridge by ID (if it exists)."""
        if (bridge := self.coordinator.data.bridges.get(bridge_id)) is None:
            LOGGER.debug("Entity references a non-existent bridge ID: %s", bridge_id)
            return None
        return bridge

    @callback
    def _async_update_bridge_id(self) -> None:
        """Update the entity's bridge ID if it has changed.

        Sensors can move to other bridges based on signal strength, etc.
        """
        sensor = self.coordinator.data.sensors[self._sensor_id]

        # If the bridge ID hasn't changed, return:
        if self._bridge_id == sensor.bridge.id:
            return

        # If the bridge doesn't exist, return:
        if (bridge := self._async_get_bridge(sensor.bridge.id)) is None:
            return

        self._bridge_id = sensor.bridge.id

        device_registry = dr.async_get(self.hass)
        this_device = device_registry.async_get_device(
            identifiers={(DOMAIN, sensor.hardware_id)}
        )
        bridge = self.coordinator.data.bridges[self._bridge_id]
        bridge_device = device_registry.async_get_device(
            identifiers={(DOMAIN, bridge.hardware_id)}
        )

        if not bridge_device or not this_device:
            return

        device_registry.async_update_device(
            this_device.id, via_device_id=bridge_device.id
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        if self._listener_id in self.coordinator.data.listeners:
            self._async_update_bridge_id()
        super()._handle_coordinator_update()
