"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast

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
from homeassistant.helpers import device_registry, discovery
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

_SERVICE_MAP = {
    "light_flash": "trigger_remote_light_flash",
    "sound_horn": "trigger_remote_horn",
    "activate_air_conditioning": "trigger_remote_air_conditioning",
    "deactivate_air_conditioning": "trigger_remote_air_conditioning_stop",
    "find_vehicle": "trigger_remote_vehicle_finder",
}

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

    # Service to manually trigger updates for all accounts.
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, _async_update_all)

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

    def execute_service(call: ServiceCall) -> None:
        """Execute a service for a vehicle."""
        _LOGGER.warning(
            "BMW Connected Drive services are deprecated. Please migrate to the dedicated button entities. "
            "See https://www.home-assistant.io/integrations/bmw_connected_drive/#buttons for details"
        )

        vin: str | None = call.data.get(ATTR_VIN)
        device_id: str | None = call.data.get(CONF_DEVICE_ID)

        vehicle: ConnectedDriveVehicle | None = None

        if not vin and device_id:
            # If vin is None, device_id must be set (given by SERVICE_SCHEMA)
            if not (device := device_registry.async_get(hass).async_get(device_id)):
                _LOGGER.error("Could not find a device for id: %s", device_id)
                return
            vin = next(iter(device.identifiers))[1]
        else:
            vin = cast(str, vin)

        # Double check for read_only accounts as another account could create the services
        for entry_data in [
            e
            for e in hass.data[DOMAIN][DATA_ENTRIES].values()
            if not e[CONF_ACCOUNT].read_only
        ]:
            account: ConnectedDriveAccount = entry_data[CONF_ACCOUNT].account
            if vehicle := account.get_vehicle(vin):
                break
        if not vehicle:
            _LOGGER.error("Could not find a vehicle for VIN %s", vin)
            return
        function_name = _SERVICE_MAP[call.service]
        function_call = getattr(vehicle.remote_services, function_name)
        function_call()

        if call.service in [
            "find_vehicle",
            "activate_air_conditioning",
            "deactivate_air_conditioning",
        ]:
            cd_account.update()

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
