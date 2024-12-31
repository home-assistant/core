"""Platform to retrieve Mawaqit prayer times information for Home Assistant."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from . import utils
from .const import (
    DATA_UPDATED,
    DOMAIN,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
    PRAYER_TIMES_ICON,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mawaqit prayer times sensor platform."""

    client = hass.data[DOMAIN]
    if not client:
        _LOGGER.error("Error retrieving client object")

    entities = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type in [
            "Fajr",
            "Shurouq",
            "Dhuhr",
            "Asr",
            "Maghrib",
            "Isha",
            "Jumua",
            "Jumua 2",  # "Aid" and "Aid 2",
            "Fajr Iqama",
            "Shurouq Iqama",
            "Dhuhr Iqama",
            "Asr Iqama",
            "Maghrib Iqama",
            "Isha Iqama",
            "Next Salat Name",
            "Next Salat Time",
            "Next Salat Preparation",
        ]:
            sensor = MawaqitPrayerTimeSensor(sensor_type, client)
            entities.append(sensor)
    async_add_entities(entities, True)

    name = "My Mosque"
    sensor1 = [MyMosqueSensor(name, hass)]
    async_add_entities(sensor1, True)


class MawaqitPrayerTimeSensor(SensorEntity):
    """Representation of an Mawaqit prayer time sensor."""

    def __init__(self, sensor_type, client) -> None:
        """Initialize the Mawaqit prayer time sensor."""
        self.sensor_type = sensor_type
        self.client = client

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.sensor_type} {SENSOR_TYPES[self.sensor_type]}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return self.sensor_type

    @property
    def icon(self) -> str:
        """Icon to display in the front end."""
        return PRAYER_TIMES_ICON

    @property
    def native_value(self):
        """Return the state of the sensor.  .astimezone(dt_util.UTC)."""
        if self.sensor_type in [
            "Fajr",
            "Shurouq",
            "Dhuhr",
            "Asr",
            "Maghrib",
            "Isha",
            "Jumua",
            "Jumua 2",  # "Aid", "Aid 2",
            "Fajr Iqama",
            "Shurouq Iqama",
            "Dhuhr Iqama",
            "Asr Iqama",
            "Maghrib Iqama",
            "Isha Iqama",
            "Next Salat Time",
            "Next Salat Preparation",
        ]:
            time = self.client.prayer_times_info.get(self.sensor_type)
            _LOGGER.debug("[;] before %s Time: %s", self.sensor_type, time)
            if time is not None:
                _LOGGER.debug(
                    "[;] %s Time: %s", self.sensor_type, time.astimezone(dt_util.UTC)
                )
                return time.astimezone(dt_util.UTC)

            return None

        return self.client.prayer_times_info.get(self.sensor_type)

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        if self.sensor_type in [
            "Fajr",
            "Shurouq",
            "Dhuhr",
            "Asr",
            "Maghrib",
            "Isha",
            "Jumua",
            "Jumua 2",  # "Aid", "Aid 2",
            "Fajr Iqama",
            "Shurouq Iqama",
            "Dhuhr Iqama",
            "Asr Iqama",
            "Maghrib Iqama",
            "Isha Iqama",
            "Next Salat Time",
            "Next Salat Preparation",
        ]:
            return SensorDeviceClass.TIMESTAMP
        return None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DATA_UPDATED, self.async_write_ha_state)
        )


class MyMosqueSensor(SensorEntity):
    """Representation of a mosque sensor."""

    def __init__(self, name, hass: HomeAssistant) -> None:
        """Initialize the mosque sensor."""
        self.hass = hass
        self._attributes: dict[str, Any] = {}
        self._name = name
        self._state = None
        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        self._latitude = latitude
        self._longitude = longitude
        self.store: Store = Store(
            self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY
        )

    async def async_update(self) -> None:
        """Get the latest data from the Mawaqit API."""
        data_my_mosque_NN = await utils.read_my_mosque_NN_file(self.store)

        for k, v in data_my_mosque_NN.items():
            if str(k) != "uuid" and str(k) != "id" and str(k) != "slug":
                self._attributes[k] = str(v)

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._attributes["name"]

    @property
    def icon(self) -> str | None:
        """Return the icon of the sensor."""
        return "mdi:mosque"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes for the sensor."""
        return self._attributes
