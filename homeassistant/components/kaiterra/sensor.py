"""Support for Kaiterra temperature and humidity sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, UnitOfTemperature
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import KaiterraConfigEntry
from .const import DISPATCHER_KAITERRA, SUBENTRY_TYPE_DEVICE


@dataclass(frozen=True, kw_only=True)
class KaiterraSensorEntityDescription(SensorEntityDescription):
    """Describe Kaiterra sensor entities."""

    suffix: str


SENSORS = (
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
)


async def async_setup_entry(
    hass,
    entry: KaiterraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kaiterra sensors from a config entry."""
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
    """Representation of a Kaiterra sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        api,
        name: str,
        device_id: str,
        description: KaiterraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self._device_id = device_id
        self.entity_description = description
        self._attr_name = f"{name} {description.suffix}"
        self._attr_unique_id = f"{device_id}_{description.suffix.lower()}"

    @property
    def _sensor(self) -> dict[str, Any]:
        """Return sensor data."""
        data = self._api.data.get(self._device_id, {}).get(self.entity_description.key)
        if isinstance(data, dict):
            return data
        return {}

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return bool(self._api.data.get(self._device_id))

    @property
    def native_value(self) -> StateType:
        """Return the current state."""
        value = self._sensor.get("value")
        if isinstance(value, str | int | float):
            return value
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        value = self._sensor.get("units")
        if not isinstance(value, str):
            return None
        if value == "F":
            return UnitOfTemperature.FAHRENHEIT
        if value == "C":
            return UnitOfTemperature.CELSIUS
        return value

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_KAITERRA, self.async_write_ha_state
            )
        )
