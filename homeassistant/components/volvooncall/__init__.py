"""Support for Volvo On Call."""

import logging

from aiohttp.client_exceptions import ClientResponseError
import async_timeout
import voluptuous as vol
from volvooncall import Connection
from volvooncall.dashboard import Instrument

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_MUTABLE,
    CONF_SCANDINAVIAN_MILES,
    CONF_SERVICE_URL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
    RESOURCES,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_METRIC,
    UNIT_SYSTEM_SCANDINAVIAN_MILES,
    VOLVO_DISCOVERY_NEW,
)
from .errors import InvalidAuth

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): vol.All(cv.time_period, vol.Clamp(min=DEFAULT_UPDATE_INTERVAL)),
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
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Migrate from YAML to ConfigEntry."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}

    if not hass.config_entries.async_entries(DOMAIN):
        new_conf = {}
        new_conf[CONF_USERNAME] = config[DOMAIN][CONF_USERNAME]
        new_conf[CONF_PASSWORD] = config[DOMAIN][CONF_PASSWORD]
        new_conf[CONF_REGION] = config[DOMAIN].get(CONF_REGION)
        new_conf[CONF_SCANDINAVIAN_MILES] = config[DOMAIN][CONF_SCANDINAVIAN_MILES]
        new_conf[CONF_MUTABLE] = config[DOMAIN][CONF_MUTABLE]

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=new_conf
            )
        )

        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version=None,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )

    return True


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

    coordinator = hass.data[DOMAIN][entry.entry_id] = VolvoUpdateCoordinator(
        hass, volvo_data
    )

    await coordinator.async_config_entry_first_refresh()

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
            await self.volvo_data.update()


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
