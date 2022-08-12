"""Support for Volvo On Call."""

import logging

import async_timeout
from volvooncall import Connection
from volvooncall.dashboard import Instrument

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_MUTABLE,
    CONF_SCANDINAVIAN_MILES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .errors import AuthenticationError

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Migrate from YAML to ConfigEntry."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}

    if not hass.config_entries.async_entries(DOMAIN):
        new_conf = {}
        new_conf[CONF_USERNAME] = config[DOMAIN].get(CONF_USERNAME)
        new_conf[CONF_PASSWORD] = config[DOMAIN].get(CONF_PASSWORD)
        new_conf[CONF_REGION] = config[DOMAIN].get(CONF_REGION)
        new_conf[CONF_SCANDINAVIAN_MILES] = config[DOMAIN].get(CONF_SCANDINAVIAN_MILES)
        new_conf[CONF_MUTABLE] = config[DOMAIN].get(CONF_MUTABLE)
        if new_conf[CONF_MUTABLE] is None:
            new_conf[CONF_MUTABLE] = True

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=new_conf
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the Volvo On Call component from a ConfigEntry."""
    session = async_get_clientsession(hass)

    connection = Connection(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        service_url=None,
        region=entry.data[CONF_REGION],
    )

    hass.data.setdefault(DOMAIN, {})

    volvo_data = VolvoData(hass, connection, entry)

    hass.data[DOMAIN][entry.entry_id] = VolvoUpdateCoordinator(hass, volvo_data)

    return await volvo_data.update()


class VolvoData:
    """Hold component state."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: Connection,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the component state."""
        self.hass = hass
        self.vehicles: set[str] = set()
        self.instruments: set[Instrument] = set()
        self.config_entry = entry
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
            mutable=self.config_entry.data[CONF_MUTABLE],
            scandinavian_miles=self.config_entry.data[CONF_SCANDINAVIAN_MILES],
        )

        for instrument in (
            instrument
            for instrument in dashboard.instruments
            if instrument.component in PLATFORMS
        ):
            self.instruments.add(instrument)

        for platform in PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

    async def update(self):
        """Update status from the online service."""
        if not await self.connection.update(journal=True):
            return False

        for vehicle in self.connection.vehicles:
            if vehicle.vin not in self.vehicles:
                self.discover_vehicle(vehicle)

        return True

    async def auth_is_valid(self):
        """Check if provided username/password/region authenticate."""
        try:
            await self.connection.get("customeraccounts")
        except Exception as exc:
            raise AuthenticationError from exc

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
