"""Support for Volvo On Call."""
from datetime import timedelta
import logging

import voluptuous as vol
from volvooncall import Connection

from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

DOMAIN = "volvooncall"

DATA_KEY = DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_UPDATE_INTERVAL = timedelta(minutes=1)
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

CONF_REGION = "region"
CONF_SERVICE_URL = "service_url"
CONF_SCANDINAVIAN_MILES = "scandinavian_miles"
CONF_MUTABLE = "mutable"

SIGNAL_STATE_UPDATED = f"{DOMAIN}.updated"

COMPONENTS = {
    "sensor": "sensor",
    "binary_sensor": "binary_sensor",
    "lock": "lock",
    "device_tracker": "device_tracker",
    "switch": "switch",
}

RESOURCES = [
    "position",
    "lock",
    "heater",
    "odometer",
    "trip_meter1",
    "trip_meter2",
    "fuel_amount",
    "fuel_amount_level",
    "average_fuel_consumption",
    "distance_to_empty",
    "washer_fluid_level",
    "brake_fluid",
    "service_warning_status",
    "bulb_failures",
    "battery_range",
    "battery_level",
    "time_to_fully_charged",
    "battery_charge_status",
    "engine_start",
    "last_trip",
    "is_engine_running",
    "doors_hood_open",
    "doors_front_left_door_open",
    "doors_front_right_door_open",
    "doors_rear_left_door_open",
    "doors_rear_right_door_open",
    "windows_front_left_window_open",
    "windows_front_right_window_open",
    "windows_rear_left_window_open",
    "windows_rear_right_window_open",
    "tyre_pressure_front_left_tyre_pressure",
    "tyre_pressure_front_right_tyre_pressure",
    "tyre_pressure_rear_left_tyre_pressure",
    "tyre_pressure_rear_right_tyre_pressure",
    "any_door_open",
    "any_window_open",
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)),
                vol.Optional(CONF_NAME, default={}): cv.schema_with_slug_keys(
                    cv.string
                ),
                vol.Optional(CONF_RESOURCES): vol.All(
                    cv.ensure_list, [vol.In(RESOURCES)]
                ),
                vol.Optional(CONF_REGION): cv.string,
                vol.Optional(CONF_SERVICE_URL): cv.string,
                vol.Optional(CONF_MUTABLE, default=True): cv.boolean,
                vol.Optional(CONF_SCANDINAVIAN_MILES, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Volvo On Call component."""
    session = async_get_clientsession(hass)

    connection = Connection(
        session=session,
        username=config[DOMAIN].get(CONF_USERNAME),
        password=config[DOMAIN].get(CONF_PASSWORD),
        service_url=config[DOMAIN].get(CONF_SERVICE_URL),
        region=config[DOMAIN].get(CONF_REGION),
    )

    interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    data = hass.data[DATA_KEY] = VolvoData(config)

    def is_enabled(attr):
        """Return true if the user has enabled the resource."""
        return attr in config[DOMAIN].get(CONF_RESOURCES, [attr])

    def discover_vehicle(vehicle):
        """Load relevant platforms."""
        data.vehicles.add(vehicle.vin)

        dashboard = vehicle.dashboard(
            mutable=config[DOMAIN][CONF_MUTABLE],
            scandinavian_miles=config[DOMAIN][CONF_SCANDINAVIAN_MILES],
        )

        for instrument in (
            instrument
            for instrument in dashboard.instruments
            if instrument.component in COMPONENTS and is_enabled(instrument.slug_attr)
        ):

            data.instruments.add(instrument)

            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    COMPONENTS[instrument.component],
                    DOMAIN,
                    (vehicle.vin, instrument.component, instrument.attr),
                    config,
                )
            )

    async def update(now):
        """Update status from the online service."""
        try:
            if not await connection.update(journal=True):
                _LOGGER.warning("Could not query server")
                return False

            for vehicle in connection.vehicles:
                if vehicle.vin not in data.vehicles:
                    discover_vehicle(vehicle)

            async_dispatcher_send(hass, SIGNAL_STATE_UPDATED)

            return True
        finally:
            async_track_point_in_utc_time(hass, update, utcnow() + interval)

    _LOGGER.info("Logging in to service")
    return await update(utcnow())


class VolvoData:
    """Hold component state."""

    def __init__(self, config):
        """Initialize the component state."""
        self.vehicles = set()
        self.instruments = set()
        self.config = config[DOMAIN]
        self.names = self.config.get(CONF_NAME)

    def instrument(self, vin, component, attr):
        """Return corresponding instrument."""
        return next(
            (
                instrument
                for instrument in self.instruments
                if instrument.vehicle.vin == vin
                and instrument.component == component
                and instrument.attr == attr
            ),
            None,
        )

    def vehicle_name(self, vehicle):
        """Provide a friendly name for a vehicle."""
        if (
            vehicle.registration_number and vehicle.registration_number.lower()
        ) in self.names:
            return self.names[vehicle.registration_number.lower()]
        if vehicle.vin and vehicle.vin.lower() in self.names:
            return self.names[vehicle.vin.lower()]
        if vehicle.registration_number:
            return vehicle.registration_number
        if vehicle.vin:
            return vehicle.vin
        return ""


class VolvoEntity(Entity):
    """Base class for all VOC entities."""

    def __init__(self, data, vin, component, attribute):
        """Initialize the entity."""
        self.data = data
        self.vin = vin
        self.component = component
        self.attribute = attribute

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STATE_UPDATED, self.async_write_ha_state
            )
        )

    @property
    def instrument(self):
        """Return corresponding instrument."""
        return self.data.instrument(self.vin, self.component, self.attribute)

    @property
    def icon(self):
        """Return the icon."""
        return self.instrument.icon

    @property
    def vehicle(self):
        """Return vehicle."""
        return self.instrument.vehicle

    @property
    def _entity_name(self):
        return self.instrument.name

    @property
    def _vehicle_name(self):
        return self.data.vehicle_name(self.vehicle)

    @property
    def name(self):
        """Return full name of the entity."""
        return f"{self._vehicle_name} {self._entity_name}"

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return dict(
            self.instrument.attributes,
            model=f"{self.vehicle.vehicle_type}/{self.vehicle.model_year}",
        )
