"""The DroneMobile integration."""
import asyncio
from datetime import timedelta
import json
import logging

import async_timeout
from drone_mobile import Vehicle
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_UNIT,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_ID,
    DEFAULT_UNIT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    VEHICLE,
)

PLATFORMS = ["lock", "sensor", "switch", "device_tracker"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up DroneMobile from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    vehicleID = entry.data[CONF_VEHICLE_ID]
    updateInterval = timedelta(seconds=(entry.data[CONF_UPDATE_INTERVAL] * 60))

    coordinator = DroneMobileDataUpdateCoordinator(
        hass, username, password, updateInterval, vehicleID
    )

    if not entry.options:
        await async_update_options(hass, entry)

    await coordinator.async_config_entry_first_refresh()  # Get initial data

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    async def async_refresh_device_status_service(self):
        await hass.async_add_executor_job(refresh_device_status, hass, coordinator)
        await coordinator.async_refresh()

    async def async_dump_device_data_service(self):
        await hass.async_add_executor_job(dump_device_data, hass, coordinator)

    async def async_clear_temp_token_service(self):
        await hass.async_add_executor_job(clear_temp_token, hass, coordinator)

    async def async_replace_token_service(self):
        await hass.async_add_executor_job(replace_token, hass, coordinator)

    hass.services.async_register(
        DOMAIN,
        f"refresh_device_status_{coordinator.data['vehicle_name'].replace(' ', '_')}",
        async_refresh_device_status_service,
    )

    hass.services.async_register(
        DOMAIN,
        f"dump_device_data_{coordinator.data['vehicle_name'].replace(' ', '_')}",
        async_dump_device_data_service,
    )

    hass.services.async_register(
        DOMAIN,
        "clear_temp_token",
        async_clear_temp_token_service,
    )

    hass.services.async_register(
        DOMAIN,
        "replace_token",
        async_replace_token_service,
    )

    return True


async def async_update_options(hass, config_entry):
    options = {
        CONF_UNIT: config_entry.data.get(CONF_UNIT, DEFAULT_UNIT),
        CONF_UPDATE_INTERVAL: config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        ),
    }
    hass.config_entries.async_update_entry(config_entry, options=options)


def refresh_device_status(hass, coordinator):
    _LOGGER.debug("Refreshing Device Status")
    response = coordinator.vehicle.device_status(coordinator.data["device_key"])
    coordinator.update_data_from_response(coordinator, response)


def dump_device_data(hass, coordinator):
    _LOGGER.debug("Dumping Device Data")
    with open(
        "./drone_mobile_device_data_" + coordinator.data["vehicle_name"] + ".txt", "w"
    ) as outfile:
        json.dump(coordinator.data, outfile)


def clear_temp_token(hass, coordinator):
    _LOGGER.debug("Clearing Tokens")
    coordinator.vehicle.clearTempToken()


def replace_token(hass, coordinator):
    _LOGGER.debug("Replacing Tokens")
    coordinator.vehicle.replaceToken()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class DroneMobileDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to handle fetching new data about the vehicle."""

    def __init__(self, hass, username, password, updateInterval, vehicleID):
        """Initialize the coordinator and set up the Vehicle object."""
        self._hass = hass
        self.username = username
        self.password = password
        self.vehicle = Vehicle(username, password)
        self._vehicleID = vehicleID
        self._available = True

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=updateInterval,
        )

    async def _async_update_data(self):
        """Fetch data from DroneMobile."""

        _LOGGER.debug(f"Retrieving vehicles for DroneMobile account")

        try:
            async with async_timeout.timeout(30):
                vehicle = await self._hass.async_add_executor_job(
                    self.vehicle.vehicle_status,
                    self._vehicleID,  # Fetch new vehicle status
                )

                # If data has now been fetched but was previously unavailable, log and reset
                if not self._available:
                    _LOGGER.debug(f"Restored connection to DroneMobile")
                    self._available = True

                return vehicle

        except Exception as ex:
            self._available = False  # Mark as unavailable
            raise UpdateFailed(f"Error communicating with DroneMobile") from ex

    def update_data_from_response(self, coordinator, json_command_response):
        if json_command_response["command_success"]:
            """Overwrite values in coordinator data to update and match returned value."""
            for key in json_command_response:
                if key == "latitude" or key == "longitude" or key == "latlng":
                    if key not in coordinator.data["last_known_state"]:
                        coordinator.data["last_known_state"][
                            key
                        ] = json_command_response[key]
                if key == "controller":
                    for key in json_command_response["controller"]:
                        if key in coordinator.data["last_known_state"]["controller"]:
                            coordinator.data["last_known_state"]["controller"][
                                key
                            ] = json_command_response["controller"][key]
                elif key in coordinator.data["last_known_state"]:
                    coordinator.data["last_known_state"][key] = json_command_response[
                        key
                    ]
                elif key in coordinator.data:
                    coordinator.data[key] = json_command_response[key]
        else:
            _LOGGER.warning(
                "Unable to send "
                + json_command_response["command_sent"]
                + " command to "
                + coordinator.data["vehicle_name"]
                + "."
            )


class DroneMobileEntity(CoordinatorEntity):
    """Defines a base DroneMobile entity."""

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        coordinator: DroneMobileDataUpdateCoordinator,
    ):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self.coordinator.data['id']}-{self._device_id}"

    @property
    def device_info(self):
        """Return device information about this device."""
        if self._device_id is None:
            return None

        return {
            "identifiers": {(DOMAIN, self.coordinator.data["id"])},
            "name": self.coordinator.data["vehicle_name"],
            "model": self.coordinator.data["last_known_state"]["controller_model"],
            "manufacturer": MANUFACTURER,
        }
