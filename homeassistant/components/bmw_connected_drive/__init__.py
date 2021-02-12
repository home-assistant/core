"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

import asyncio
import logging

from bimmer_connected.account import ConnectedDriveAccount
from bimmer_connected.country_selector import get_region_from_name
import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_ACCOUNT,
    CONF_ALLOWED_REGIONS,
    CONF_READ_ONLY,
    CONF_USE_LOCATION,
    DATA_ENTRIES,
    DATA_HASS_CONFIG,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "bmw_connected_drive"
ATTR_VIN = "vin"

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_REGION): vol.In(CONF_ALLOWED_REGIONS),
        vol.Optional(CONF_READ_ONLY): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: {cv.string: ACCOUNT_SCHEMA}}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_VIN): cv.string})

DEFAULT_OPTIONS = {
    CONF_READ_ONLY: False,
    CONF_USE_LOCATION: False,
}

BMW_PLATFORMS = ["binary_sensor", "device_tracker", "lock", "notify", "sensor"]
UPDATE_INTERVAL = 5  # in minutes

SERVICE_UPDATE_STATE = "update_state"

_SERVICE_MAP = {
    "light_flash": "trigger_remote_light_flash",
    "sound_horn": "trigger_remote_horn",
    "activate_air_conditioning": "trigger_remote_air_conditioning",
    "find_vehicle": "trigger_remote_vehicle_finder",
}

UNDO_UPDATE_LISTENER = "undo_update_listener"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the BMW Connected Drive component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    if DOMAIN in config:
        for entry_config in config[DOMAIN].values():
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


@callback
def _async_migrate_options_from_data_if_missing(hass, entry):
    data = dict(entry.data)
    options = dict(entry.options)

    if CONF_READ_ONLY in data or list(options) != list(DEFAULT_OPTIONS):
        options = dict(DEFAULT_OPTIONS, **options)
        options[CONF_READ_ONLY] = data.pop(CONF_READ_ONLY, False)

        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
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

    async def _async_update_all(service_call=None):
        """Update all BMW accounts."""
        await hass.async_add_executor_job(_update_all)

    def _update_all() -> None:
        """Update all BMW accounts."""
        for entry in hass.data[DOMAIN][DATA_ENTRIES].values():
            entry[CONF_ACCOUNT].update()

    # Add update listener for config entry changes (options)
    undo_listener = entry.add_update_listener(update_listener)

    hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id] = {
        CONF_ACCOUNT: account,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    # Service to manually trigger updates for all accounts.
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, _async_update_all)

    await _async_update_all()

    for platform in BMW_PLATFORMS:
        if platform != NOTIFY_DOMAIN:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            NOTIFY_DOMAIN,
            DOMAIN,
            {CONF_NAME: DOMAIN},
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in BMW_PLATFORMS
                if component != NOTIFY_DOMAIN
            ]
        )
    )

    # Only remove services if it is the last account and not read only
    if (
        len(hass.data[DOMAIN][DATA_ENTRIES]) == 1
        and not hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][CONF_ACCOUNT].read_only
    ):
        services = list(_SERVICE_MAP) + [SERVICE_UPDATE_STATE]
        for service in services:
            hass.services.async_remove(DOMAIN, service)

    for vehicle in hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][
        CONF_ACCOUNT
    ].account.vehicles:
        hass.services.async_remove(NOTIFY_DOMAIN, slugify(f"{DOMAIN}_{vehicle.name}"))

    if unload_ok:
        hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN][DATA_ENTRIES].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def setup_account(entry: ConfigEntry, hass, name: str) -> BMWConnectedDriveAccount:
    """Set up a new BMWConnectedDriveAccount based on the config."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    region = entry.data[CONF_REGION]
    read_only = entry.options[CONF_READ_ONLY]
    use_location = entry.options[CONF_USE_LOCATION]

    _LOGGER.debug("Adding new account %s", name)

    pos = (
        (hass.config.latitude, hass.config.longitude) if use_location else (None, None)
    )
    cd_account = BMWConnectedDriveAccount(
        username, password, region, name, read_only, *pos
    )

    def execute_service(call):
        """Execute a service for a vehicle."""
        vin = call.data[ATTR_VIN]
        vehicle = None
        # Double check for read_only accounts as another account could create the services
        for entry_data in [
            e
            for e in hass.data[DOMAIN][DATA_ENTRIES].values()
            if not e[CONF_ACCOUNT].read_only
        ]:
            vehicle = entry_data[CONF_ACCOUNT].account.get_vehicle(vin)
            if vehicle:
                break
        if not vehicle:
            _LOGGER.error("Could not find a vehicle for VIN %s", vin)
            return
        function_name = _SERVICE_MAP[call.service]
        function_call = getattr(vehicle.remote_services, function_name)
        function_call()

    if not read_only:
        # register the remote services
        for service in _SERVICE_MAP:
            hass.services.register(
                DOMAIN, service, execute_service, schema=SERVICE_SCHEMA
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
        lat=None,
        lon=None,
    ) -> None:
        """Initialize account."""
        region = get_region_from_name(region_str)

        self.read_only = read_only
        self.account = ConnectedDriveAccount(username, password, region)
        self.name = name
        self._update_listeners = []

        # Set observer position once for older cars to be in range for
        # GPS position (pre-7/2014, <2km) and get new data from API
        if lat and lon:
            self.account.set_observer_position(lat, lon)
            self.account.update_vehicle_states()

    def update(self, *_):
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

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)


class BMWConnectedDriveBaseEntity(Entity):
    """Common base for BMW entities."""

    def __init__(self, account, vehicle):
        """Initialize sensor."""
        self._account = account
        self._vehicle = vehicle
        self._attrs = {
            "car": self._vehicle.name,
            "vin": self._vehicle.vin,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {(DOMAIN, self._vehicle.vin)},
            "name": f'{self._vehicle.attributes.get("brand")} {self._vehicle.name}',
            "model": self._vehicle.name,
            "manufacturer": self._vehicle.attributes.get("brand"),
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attrs

    @property
    def should_poll(self):
        """Do not poll this class.

        Updates are triggered from BMWConnectedDriveAccount.
        """
        return False

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
