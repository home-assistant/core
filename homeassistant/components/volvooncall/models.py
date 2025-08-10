"""Support for Volvo On Call."""

from aiohttp.client_exceptions import ClientResponseError
from volvooncall import Connection
from volvooncall.dashboard import Instrument

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_MUTABLE,
    PLATFORMS,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_SCANDINAVIAN_MILES,
    VOLVO_DISCOVERY_NEW,
)
from .errors import InvalidAuth


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
