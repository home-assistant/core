"""Support for Notion."""
import asyncio
from datetime import timedelta

from aionotion import async_get_client
from aionotion.errors import InvalidCredentialsError, NotionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DATA_COORDINATOR, DOMAIN, LOGGER

PLATFORMS = ["binary_sensor", "sensor"]

ATTR_SYSTEM_MODE = "system_mode"
ATTR_SYSTEM_NAME = "system_name"

DEFAULT_ATTRIBUTION = "Data provided by Notion"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Notion component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Notion as a config entry."""
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session
        )
    except InvalidCredentialsError:
        LOGGER.error("Invalid username and/or password")
        return False
    except NotionError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    async def async_update():
        """Get the latest data from the Notion API."""
        data = {"bridges": {}, "sensors": {}, "tasks": {}}
        tasks = {
            "bridges": client.bridge.async_all(),
            "sensors": client.sensor.async_all(),
            "tasks": client.task.async_all(),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for attr, result in zip(tasks, results):
            if isinstance(result, NotionError):
                raise UpdateFailed(
                    f"There was a Notion error while updating {attr}: {result}"
                )
            if isinstance(result, Exception):
                raise UpdateFailed(
                    f"There was an unknown error while updating {attr}: {result}"
                )

            for item in result:
                if attr == "bridges" and item["id"] not in data["bridges"]:
                    # If a new bridge is discovered, register it:
                    hass.async_create_task(async_register_new_bridge(hass, item, entry))
                data[attr][item["id"]] = item

        return data

    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][
        entry.entry_id
    ] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.data[CONF_USERNAME],
        update_interval=DEFAULT_SCAN_INTERVAL,
        update_method=async_update,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Notion config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)

    return unload_ok


async def async_register_new_bridge(
    hass: HomeAssistant, bridge: dict, entry: ConfigEntry
):
    """Register a new bridge."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, bridge["hardware_id"])},
        manufacturer="Silicon Labs",
        model=bridge["hardware_revision"],
        name=bridge["name"] or bridge["id"],
        sw_version=bridge["firmware_version"]["wifi"],
    )


class NotionEntity(CoordinatorEntity):
    """Define a base Notion entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        task_id: str,
        sensor_id: str,
        bridge_id: str,
        system_id: str,
        name: str,
        device_class: str,
    ):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._bridge_id = bridge_id
        self._device_class = device_class
        self._name = name
        self._sensor_id = sensor_id
        self._state = None
        self._system_id = system_id
        self._unique_id = (
            f'{sensor_id}_{self.coordinator.data["tasks"][task_id]["task_type"]}'
        )
        self.task_id = task_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.task_id in self.coordinator.data["tasks"]
            and self._state
        )

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def device_info(self) -> dict:
        """Return device registry information for this entity."""
        bridge = self.coordinator.data["bridges"].get(self._bridge_id, {})
        sensor = self.coordinator.data["sensors"][self._sensor_id]

        return {
            "identifiers": {(DOMAIN, sensor["hardware_id"])},
            "manufacturer": "Silicon Labs",
            "model": sensor["hardware_revision"],
            "name": sensor["name"],
            "sw_version": sensor["firmware_version"],
            "via_device": (DOMAIN, bridge.get("hardware_id")),
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        sensor = self.coordinator.data["sensors"][self._sensor_id]
        return f'{sensor["name"]}: {self._name}'

    @property
    def unique_id(self) -> str:
        """Return a unique, unchanging string that represents this entity."""
        return self._unique_id

    async def _async_update_bridge_id(self) -> None:
        """Update the entity's bridge ID if it has changed.

        Sensors can move to other bridges based on signal strength, etc.
        """
        sensor = self.coordinator.data["sensors"][self._sensor_id]

        # If the sensor's bridge ID is the same as what we had before or if it points
        # to a bridge that doesn't exist (which can happen due to a Notion API bug),
        # return immediately:
        if (
            self._bridge_id == sensor["bridge"]["id"]
            or sensor["bridge"]["id"] not in self.coordinator.data["bridges"]
        ):
            return

        self._bridge_id = sensor["bridge"]["id"]

        device_registry = await dr.async_get_registry(self.hass)
        bridge = self.coordinator.data["bridges"][self._bridge_id]
        bridge_device = device_registry.async_get_device(
            {(DOMAIN, bridge["hardware_id"])}
        )
        this_device = device_registry.async_get_device(
            {(DOMAIN, sensor["hardware_id"])}
        )

        device_registry.async_update_device(
            this_device.id, via_device_id=bridge_device.id
        )

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self):
        """Respond to a DataUpdateCoordinator update."""
        if self.task_id in self.coordinator.data["tasks"]:
            self.hass.async_create_task(self._async_update_bridge_id())
            self._async_update_from_latest_data()

        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._async_update_from_latest_data()
