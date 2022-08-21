"""Support for Volvo On Call."""
from datetime import timedelta
import logging

import async_timeout
import voluptuous as vol
from volvooncall import Connection
from volvooncall.dashboard import Instrument

from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

DOMAIN = "volvooncall"

DATA_KEY = DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

CONF_SERVICE_URL = "service_url"
CONF_SCANDINAVIAN_MILES = "scandinavian_miles"
CONF_MUTABLE = "mutable"

SIGNAL_STATE_UPDATED = f"{DOMAIN}.updated"

PLATFORMS = {
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
    "average_speed",
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
    "doors_tailgate_open",
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
        DOMAIN: vol.All(
            cv.deprecated(CONF_SCAN_INTERVAL),
            cv.deprecated(CONF_NAME),
            cv.deprecated(CONF_RESOURCES),
            vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): vol.All(
                        cv.time_period, vol.Clamp(min=DEFAULT_UPDATE_INTERVAL)
                    ),  # ignored, using DataUpdateCoordinator instead
                    vol.Optional(CONF_NAME, default={}): cv.schema_with_slug_keys(
                        cv.string
                    ),  # ignored, users can modify names of entities in the UI
                    vol.Optional(CONF_RESOURCES): vol.All(
                        cv.ensure_list, [vol.In(RESOURCES)]
                    ),  # ignored, users can disable entities in the UI
                    vol.Optional(CONF_REGION): cv.string,
                    vol.Optional(CONF_SERVICE_URL): cv.string,
                    vol.Optional(CONF_MUTABLE, default=True): cv.boolean,
                    vol.Optional(CONF_SCANDINAVIAN_MILES, default=False): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Volvo On Call component."""
    session = async_get_clientsession(hass)

    connection = Connection(
        session=session,
        username=config[DOMAIN].get(CONF_USERNAME),
        password=config[DOMAIN].get(CONF_PASSWORD),
        service_url=config[DOMAIN].get(CONF_SERVICE_URL),
        region=config[DOMAIN].get(CONF_REGION),
    )

    hass.data[DATA_KEY] = {}

    volvo_data = VolvoData(hass, connection, config)

    hass.data[DATA_KEY] = VolvoUpdateCoordinator(hass, volvo_data)

    return await volvo_data.update()


class VolvoData:
    """Hold component state."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: Connection,
        config: ConfigType,
    ) -> None:
        """Initialize the component state."""
        self.hass = hass
        self.vehicles: set[str] = set()
        self.instruments: set[Instrument] = set()
        self.config = config
        self.connection = connection

    def instrument(self, vin, component, attr, slug_attr):
        """Return corresponding instrument."""
        return next(
            instrument
            for instrument in self.instruments
            if instrument.vehicle.vin == vin
            and instrument.component == component
            and instrument.attr == attr
            and instrument.slug_attr == slug_attr
        )

    def vehicle_name(self, vehicle):
        """Provide a friendly name for a vehicle."""
        if vehicle.registration_number and vehicle.registration_number != "UNKNOWN":
            return vehicle.registration_number
        if vehicle.vin:
            return vehicle.vin
        return "Volvo"

    def discover_vehicle(self, vehicle):
        """Load relevant platforms."""
        self.vehicles.add(vehicle.vin)

        dashboard = vehicle.dashboard(
            mutable=self.config[DOMAIN][CONF_MUTABLE],
            scandinavian_miles=self.config[DOMAIN][CONF_SCANDINAVIAN_MILES],
        )

        for instrument in (
            instrument
            for instrument in dashboard.instruments
            if instrument.component in PLATFORMS
        ):

            self.instruments.add(instrument)

            self.hass.async_create_task(
                discovery.async_load_platform(
                    self.hass,
                    PLATFORMS[instrument.component],
                    DOMAIN,
                    (
                        vehicle.vin,
                        instrument.component,
                        instrument.attr,
                        instrument.slug_attr,
                    ),
                    self.config,
                )
            )

    async def update(self):
        """Update status from the online service."""
        if not await self.connection.update(journal=True):
            return False

        for vehicle in self.connection.vehicles:
            if vehicle.vin not in self.vehicles:
                self.discover_vehicle(vehicle)

        # this is currently still needed for device_tracker, which isn't using the update coordinator yet
        async_dispatcher_send(self.hass, SIGNAL_STATE_UPDATED)

        return True


class VolvoUpdateCoordinator(DataUpdateCoordinator):
    """Volvo coordinator."""

    def __init__(self, hass: HomeAssistant, volvo_data: VolvoData) -> None:
        """Initialize the data update coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name="volvooncall",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self.volvo_data = volvo_data

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        async with async_timeout.timeout(10):
            if not await self.volvo_data.update():
                raise UpdateFailed("Error communicating with API")


class VolvoEntity(CoordinatorEntity):
    """Base class for all VOC entities."""

    def __init__(
        self,
        vin: str,
        component: str,
        attribute: str,
        slug_attr: str,
        coordinator: VolvoUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.vin = vin
        self.component = component
        self.attribute = attribute
        self.slug_attr = slug_attr

    @property
    def instrument(self):
        """Return corresponding instrument."""
        return self.coordinator.volvo_data.instrument(
            self.vin, self.component, self.attribute, self.slug_attr
        )

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
        return self.coordinator.volvo_data.vehicle_name(self.vehicle)

    @property
    def name(self):
        """Return full name of the entity."""
        return f"{self._vehicle_name} {self._entity_name}"

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return dict(
            self.instrument.attributes,
            model=f"{self.vehicle.vehicle_type}/{self.vehicle.model_year}",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        slug_override = ""
        if self.instrument.slug_override is not None:
            slug_override = f"-{self.instrument.slug_override}"
        return f"{self.vin}-{self.component}-{self.attribute}{slug_override}"
