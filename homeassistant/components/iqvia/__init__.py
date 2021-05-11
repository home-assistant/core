"""Support for IQVIA."""
import asyncio
from datetime import timedelta
from functools import partial

from pyiqvia import Client
from pyiqvia.errors import IQVIAError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_ZIP_CODE,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
    TYPE_ALLERGY_FORECAST,
    TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK,
    TYPE_ASTHMA_FORECAST,
    TYPE_ASTHMA_INDEX,
    TYPE_DISEASE_FORECAST,
    TYPE_DISEASE_INDEX,
)

DEFAULT_ATTRIBUTION = "Data provided by IQVIA™"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass, entry):
    """Set up IQVIA as config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinators = {}

    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        hass.config_entries.async_update_entry(
            entry, **{"unique_id": entry.data[CONF_ZIP_CODE]}
        )

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(entry.data[CONF_ZIP_CODE], session=websession)

    async def async_get_data_from_api(api_coro):
        """Get data from a particular API coroutine."""
        try:
            return await api_coro()
        except IQVIAError as err:
            raise UpdateFailed from err

    init_data_update_tasks = []
    for sensor_type, api_coro in [
        (TYPE_ALLERGY_FORECAST, client.allergens.extended),
        (TYPE_ALLERGY_INDEX, client.allergens.current),
        (TYPE_ALLERGY_OUTLOOK, client.allergens.outlook),
        (TYPE_ASTHMA_FORECAST, client.asthma.extended),
        (TYPE_ASTHMA_INDEX, client.asthma.current),
        (TYPE_DISEASE_FORECAST, client.disease.extended),
        (TYPE_DISEASE_INDEX, client.disease.current),
    ]:
        coordinator = coordinators[sensor_type] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{entry.data[CONF_ZIP_CODE]} {sensor_type}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            update_method=partial(async_get_data_from_api, api_coro),
        )
        init_data_update_tasks.append(coordinator.async_config_entry_first_refresh())

    await asyncio.gather(*init_data_update_tasks)

    hass.data[DOMAIN].setdefault(DATA_COORDINATOR, {})[entry.entry_id] = coordinators
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)
    return unload_ok


class IQVIAEntity(CoordinatorEntity, SensorEntity):
    """Define a base IQVIA entity."""

    def __init__(self, coordinator, entry, sensor_type, name, icon):
        """Initialize."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._entry = entry
        self._icon = icon
        self._name = name
        self._state = None
        self._type = sensor_type

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry.data[CONF_ZIP_CODE]}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "index"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            return

        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()

        if self._type == TYPE_ALLERGY_FORECAST:
            self.async_on_remove(
                self.hass.data[DOMAIN][DATA_COORDINATOR][self._entry.entry_id][
                    TYPE_ALLERGY_OUTLOOK
                ].async_add_listener(self._handle_coordinator_update)
            )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self):
        """Update the entity from the latest data."""
        raise NotImplementedError
