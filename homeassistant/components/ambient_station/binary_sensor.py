"""Support for Ambient Weather Station binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbientWeatherEntity
from .const import (
    ATTR_LAST_DATA,
    DATA_CLIENT,
    DOMAIN,
    TYPE_BATT1,
    TYPE_BATT2,
    TYPE_BATT3,
    TYPE_BATT4,
    TYPE_BATT5,
    TYPE_BATT6,
    TYPE_BATT7,
    TYPE_BATT8,
    TYPE_BATT9,
    TYPE_BATT10,
    TYPE_BATT_CO2,
    TYPE_BATTOUT,
    TYPE_PM25_BATT,
    TYPE_PM25IN_BATT,
    TYPE_RELAY1,
    TYPE_RELAY2,
    TYPE_RELAY3,
    TYPE_RELAY4,
    TYPE_RELAY5,
    TYPE_RELAY6,
    TYPE_RELAY7,
    TYPE_RELAY8,
    TYPE_RELAY9,
    TYPE_RELAY10,
)

BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key=TYPE_BATTOUT,
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT1,
        name="Battery 1",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT2,
        name="Battery 2",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT3,
        name="Battery 3",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT4,
        name="Battery 4",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT5,
        name="Battery 5",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT6,
        name="Battery 6",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT7,
        name="Battery 7",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT8,
        name="Battery 8",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT9,
        name="Battery 9",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT10,
        name="Battery 10",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_BATT_CO2,
        name="CO2 Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_PM25IN_BATT,
        name="PM25 Indoor Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_PM25_BATT,
        name="PM25 Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY1,
        name="Relay 1",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY2,
        name="Relay 2",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY3,
        name="Relay 3",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY4,
        name="Relay 4",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY5,
        name="Relay 5",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY6,
        name="Relay 6",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY7,
        name="Relay 7",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY8,
        name="Relay 8",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY9,
        name="Relay 9",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_RELAY10,
        name="Relay 10",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            AmbientWeatherBinarySensor(
                ambient, mac_address, station[ATTR_NAME], description
            )
            for description in BINARY_SENSOR_DESCRIPTIONS
            for mac_address, station in ambient.stations.items()
            if description.key in station[ATTR_LAST_DATA]
        ]
    )


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorEntity):
    """Define an Ambient binary sensor."""

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the entity."""
        state = self._ambient.stations[self._mac_address][ATTR_LAST_DATA][
            self.entity_description.key
        ]

        if self.entity_description.key in (
            TYPE_BATT1,
            TYPE_BATT10,
            TYPE_BATT2,
            TYPE_BATT3,
            TYPE_BATT4,
            TYPE_BATT5,
            TYPE_BATT6,
            TYPE_BATT7,
            TYPE_BATT8,
            TYPE_BATT9,
            TYPE_BATT_CO2,
            TYPE_BATTOUT,
            TYPE_PM25_BATT,
            TYPE_PM25IN_BATT,
        ):
            self._attr_is_on = state == 0
        else:
            self._attr_is_on = state == 1
