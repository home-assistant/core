"""Support for Kaiterra temperature and humidity sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaiterraConfigEntry
from .const import DISPATCHER_KAITERRA, SUBENTRY_TYPE_DEVICE


@dataclass(frozen=True, kw_only=True)
class KaiterraSensorEntityDescription(SensorEntityDescription):
    """Class describing Kaiterra sensor entities."""

    suffix: str


SENSORS = [
    KaiterraSensorEntityDescription(
        suffix="Temperature",
        key="rtemp",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    KaiterraSensorEntityDescription(
        suffix="Humidity",
        key="rhumid",
        device_class=SensorDeviceClass.HUMIDITY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaiterraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kaiterra temperature and humidity sensors."""
    api = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        name = subentry.data.get(CONF_NAME) or subentry.title
        device_id = subentry.data[CONF_DEVICE_ID]

        async_add_entities(
            [
                KaiterraSensor(api, name, device_id, description)
                for description in SENSORS
            ],
            config_subentry_id=subentry.subentry_id,
        )


class KaiterraSensor(SensorEntity):
    """Implementation of a Kaiterra sensor."""

    _attr_should_poll = False

    def __init__(
        self, api, name, device_id, description: KaiterraSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self._device_id = device_id
        self.entity_description = description
        self._attr_name = f"{name} {description.suffix}"
        self._attr_unique_id = f"{device_id}_{description.suffix.lower()}"

    @property
    def _sensor(self):
        """Return the sensor data."""
        return self._api.data.get(self._device_id, {}).get(
            self.entity_description.key, {}
        )

    @property
    def available(self) -> bool:
        """Return the availability of the sensor."""
        return bool(self._api.data.get(self._device_id))

    @property
    def native_value(self):
        """Return the state."""
        return self._sensor.get("value")

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        value = self._sensor.get("units")
        if not value:
            return None

        if hasattr(value, "value"):
            value = value.value

        if value == "F":
            return UnitOfTemperature.FAHRENHEIT
        if value == "C":
            return UnitOfTemperature.CELSIUS
        return value

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_KAITERRA, self.async_write_ha_state
            )
        )
