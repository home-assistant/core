"""Platform for sensor integration."""
from homeassistant.const import DEVICE_CLASS_POWER, POWER_WATT
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

import async_timeout
import logging
from datetime import timedelta

from homeassistant.const import CONF_ID
from homeassistant.components.huisbaasje.const import DOMAIN
from .const import SOURCE_TYPES, FLOW_CUBIC_METERS_PER_HOUR, POLLING_INTERVAL
from huisbaasje import (
    Huisbaasje,
    HuisbaasjeConnectionException,
    HuisbaasjeException,
    HuisbaasjeUnauthenticatedException,
)
from huisbaasje.const import SOURCE_TYPE_ELECTRICITY, SOURCE_TYPE_GAS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the sensor platform."""
    user_id = config_entry.data[CONF_ID]
    # Get the Huisbaasje client
    huisbaasje = hass.data[DOMAIN][user_id]

    async def async_update_data():
        await async_update_huisbaasje(huisbaasje)

    # Create a coordinator for polling updates
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=POLLING_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_refresh()

    async_add_entities(
        [
            HuisbaasjeSensor(
                coordinator,
                name="Electricity",
                device_class=DEVICE_CLASS_POWER,
                unit_of_measurement=POWER_WATT,
                source_type=SOURCE_TYPE_ELECTRICITY,
                icon="mdi:lightning-bolt",
            ),
            HuisbaasjeSensor(
                coordinator,
                name="Gas",
                device_class=None,
                unit_of_measurement=FLOW_CUBIC_METERS_PER_HOUR,
                source_type=SOURCE_TYPE_GAS,
                icon="mdi:fire",
            ),
        ]
    )


async def async_update_huisbaasje(huisbaasje):
    try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(10):
            current_measurements = await huisbaasje.current_measurements()

            _LOGGER.info(current_measurements)

            data = dict()

            for source_type in SOURCE_TYPES:
                data[source_type] = None
                if source_type in current_measurements.keys():
                    if current_measurements[source_type]["measurement"]:
                        data[source_type] = current_measurements[source_type][
                            "measurement"
                        ]["rate"]

            _LOGGER.info(data)

            return data
    except HuisbaasjeException as exception:
        raise UpdateFailed(f"Error communicating with API: {exception}")


class HuisbaasjeSensor(Entity):
    """Defines a Huisbaasje sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_class: str,
        source_type: str,
        unit_of_measurement: str,
        icon: str,
    ):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._device_class = device_class
        self._coordinator = coordinator
        self._unit_of_measurement = unit_of_measurement
        self._source_type = source_type
        self._icon = icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.info(self._coordinator.data)

        if self._coordinator.data and self._coordinator.data[self._source_type]:
            return self._coordinator.data[self._source_type]

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return True
        # return (
        #     self._coordinator.last_update_success
        #     and self._coordinator.data
        #     and self._coordinator.data[self._source_type]
        # )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()
