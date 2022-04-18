"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from bimmer_connected.account import ConnectedDriveAccount
from bimmer_connected.country_selector import get_region_from_name
from bimmer_connected.vehicle import ConnectedDriveVehicle
import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_ACCOUNT,
    CONF_READ_ONLY,
    DATA_ENTRIES,
    DATA_HASS_CONFIG,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "bmw_connected_drive"
ATTR_VIN = "vin"

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

SERVICE_SCHEMA = vol.Schema(
    vol.Any(
        {vol.Required(ATTR_VIN): cv.string},
        {vol.Required(CONF_DEVICE_ID): cv.string},
    )
)

DEFAULT_OPTIONS = {
    CONF_READ_ONLY: False,
}

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NOTIFY,
    Platform.SENSOR,
]
UPDATE_INTERVAL = 5  # in minutes

SERVICE_UPDATE_STATE = "update_state"

UNDO_UPDATE_LISTENER = "undo_update_listener"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BMW Connected Drive component from configuration.yaml."""
    # Store full yaml config in data for platform.NOTIFY
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    return True


@callback
def _async_migrate_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    data = dict(entry.data)
    options = dict(entry.options)

    if CONF_READ_ONLY in data or list(options) != list(DEFAULT_OPTIONS):
        options = dict(DEFAULT_OPTIONS, **options)
        options[CONF_READ_ONLY] = data.pop(CONF_READ_ONLY, False)

        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BMW Connected Drive from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_ENTRIES, {})

    _async_migrate_options_from_data_if_missing(hass, entry)

    try:
        account = await hass.async_add_executor_job(
            setup_account, entry, hass, entry.data[CONF_USERNAME]
        )
    except OSError as ex:
        raise ConfigEntryNotReady from ex

    async def _async_update_all(service_call: ServiceCall | None = None) -> None:
        """Update all BMW accounts."""
        await hass.async_add_executor_job(_update_all)

    def _update_all() -> None:
        """Update all BMW accounts."""
        for entry in hass.data[DOMAIN][DATA_ENTRIES].copy().values():
            entry[CONF_ACCOUNT].update()

    # Add update listener for config entry changes (options)
    undo_listener = entry.add_update_listener(update_listener)

    hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id] = {
        CONF_ACCOUNT: account,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await _async_update_all()

    hass.config_entries.async_setup_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    # set up notify platform, no entry support for notify platform yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: DOMAIN},
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    for vehicle in hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][
        CONF_ACCOUNT
    ].account.vehicles:
        hass.services.async_remove(NOTIFY_DOMAIN, slugify(f"{DOMAIN}_{vehicle.name}"))

    if unload_ok:
        hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN][DATA_ENTRIES].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def setup_account(
    entry: ConfigEntry, hass: HomeAssistant, name: str
) -> BMWConnectedDriveAccount:
    """Set up a new BMWConnectedDriveAccount based on the config."""
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    region: str = entry.data[CONF_REGION]
    read_only: bool = entry.options[CONF_READ_ONLY]

    _LOGGER.debug("Adding new account %s", name)

    pos = (hass.config.latitude, hass.config.longitude)
    cd_account = BMWConnectedDriveAccount(
        username, password, region, name, read_only, *pos
    )

    # update every UPDATE_INTERVAL minutes, starting now
    # this should even out the load on the servers
    now = dt_util.utcnow()
    track_utc_time_change(
        hass,
        cd_account.update,
        minute=range(now.minute % UPDATE_INTERVAL, 60, UPDATE_INTERVAL),
        second=now.second,
    )

    # Initialize
    cd_account.update()

    return cd_account


class BMWConnectedDriveAccount:
    """Representation of a BMW vehicle."""

    def __init__(
        self,
        username: str,
        password: str,
        region_str: str,
        name: str,
        read_only: bool,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        """Initialize account."""
        region = get_region_from_name(region_str)

        self.read_only = read_only
        self.account = ConnectedDriveAccount(username, password, region)
        self.name = name
        self._update_listeners: list[Callable[[], None]] = []

        # Set observer position once for older cars to be in range for
        # GPS position (pre-7/2014, <2km) and get new data from API
        if lat and lon:
            self.account.set_observer_position(lat, lon)
            self.account.update_vehicle_states()

    def update(self, *_: Any) -> None:
        """Update the state of all vehicles.

        Notify all listeners about the update.
        """
        _LOGGER.debug(
            "Updating vehicle state for account %s, notifying %d listeners",
            self.name,
            len(self._update_listeners),
        )
        try:
            self.account.update_vehicle_states()
            for listener in self._update_listeners:
                listener()
        except OSError as exception:
            _LOGGER.error(
                "Could not connect to the BMW Connected Drive portal. "
                "The vehicle state could not be updated"
            )
            _LOGGER.exception(exception)

    def add_update_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)


class BMWConnectedDriveBaseEntity(Entity):
    """Common base for BMW entities."""

    _attr_should_poll = False
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
    ) -> None:
        """Initialize sensor."""
        self._account = account
        self._vehicle = vehicle
        self._attrs: dict[str, Any] = {
            "car": self._vehicle.name,
            "vin": self._vehicle.vin,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer=vehicle.brand.name,
            model=vehicle.name,
            name=f"{vehicle.brand.name} {vehicle.name}",
        )

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
