"""Support for Volvo On Call."""

import asyncio
import logging

from aiohttp.client_exceptions import ClientResponseError
from volvooncall import Connection
from volvooncall.dashboard import Instrument

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_UNIT_SYSTEM,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MUTABLE,
    CONF_SCANDINAVIAN_MILES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_METRIC,
    UNIT_SYSTEM_SCANDINAVIAN_MILES,
    VOLVO_DISCOVERY_NEW,
)
from .errors import InvalidAuth

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Volvo On Call component from a ConfigEntry."""

    # added CONF_UNIT_SYSTEM / deprecated CONF_SCANDINAVIAN_MILES in 2022.10 to support imperial units
    if CONF_UNIT_SYSTEM not in entry.data:
        new_conf = {**entry.data}

        scandinavian_miles: bool = entry.data[CONF_SCANDINAVIAN_MILES]

        new_conf[CONF_UNIT_SYSTEM] = (
            UNIT_SYSTEM_SCANDINAVIAN_MILES if scandinavian_miles else UNIT_SYSTEM_METRIC
        )

        hass.config_entries.async_update_entry(entry, data=new_conf)

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

    coordinator = VolvoUpdateCoordinator(hass, volvo_data)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class VolvoData:
    """Hold component state."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: Connection,
        entry: ConfigEntry,
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
            scandinavian_miles=(
                self.config_entry.data[CONF_UNIT_SYSTEM]
                == UNIT_SYSTEM_SCANDINAVIAN_MILES
            ),
            usa_units=(
                self.config_entry.data[CONF_UNIT_SYSTEM] == UNIT_SYSTEM_IMPERIAL
            ),
        )

        for instrument in (
            instrument
            for instrument in dashboard.instruments
            if instrument.component in PLATFORMS
        ):
            self.instruments.add(instrument)
            async_dispatcher_send(self.hass, VOLVO_DISCOVERY_NEW, [instrument])

    async def update(self):
        """Update status from the online service."""
        try:
            await self.connection.update(journal=True)
        except ClientResponseError as ex:
            if ex.status == 401:
                raise ConfigEntryAuthFailed(ex) from ex
            raise UpdateFailed(ex) from ex

        for vehicle in self.connection.vehicles:
            if vehicle.vin not in self.vehicles:
                self.discover_vehicle(vehicle)

    async def auth_is_valid(self):
        """Check if provided username/password/region authenticate."""
        try:
            await self.connection.get("customeraccounts")
        except ClientResponseError as exc:
            raise InvalidAuth from exc


class VolvoUpdateCoordinator(DataUpdateCoordinator[None]):  # pylint: disable=hass-enforce-class-module
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

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        async with asyncio.timeout(10):
            await self.volvo_data.update()
