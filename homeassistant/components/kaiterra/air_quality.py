"""Support for Kaiterra air quality sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaiterraConfigEntry
from .const import (
    ATTR_AQI_LEVEL,
    ATTR_AQI_POLLUTANT,
    ATTR_VOC,
    DISPATCHER_KAITERRA,
    SUBENTRY_TYPE_DEVICE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaiterraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kaiterra air quality sensor."""
    api = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        name = subentry.data.get(CONF_NAME) or subentry.title
        device_id = subentry.data[CONF_DEVICE_ID]
        async_add_entities(
            [KaiterraAirQuality(api, name, device_id)],
            config_subentry_id=subentry.subentry_id,
        )


class KaiterraAirQuality(AirQualityEntity):
    """Implementation of a Kaiterra air quality sensor."""

    _attr_should_poll = False

    def __init__(self, api, name, device_id):
        """Initialize the sensor."""
        self._api = api
        self._name = f"{name} Air Quality"
        self._device_id = device_id

    def _data(self, key):
        return self._device.get(key, {}).get("value")

    @property
    def _device(self):
        return self._api.data.get(self._device_id, {})

    @property
    def available(self):
        """Return the availability of the sensor."""
        return bool(self._api.data.get(self._device_id))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._data("aqi")

    @property
    def air_quality_index_level(self):
        """Return the Air Quality Index level."""
        return self._data("aqi_level")

    @property
    def air_quality_index_pollutant(self):
        """Return the Air Quality Index level."""
        return self._data("aqi_pollutant")

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._data("rpm25c")

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._data("rpm10c")

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return self._data("rco2")

    @property
    def volatile_organic_compounds(self):
        """Return the VOC (Volatile Organic Compounds) level."""
        return self._data("rtvoc")

    @property
    def unique_id(self):
        """Return the sensor's unique id."""
        return f"{self._device_id}_air_quality"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {
            attr: value
            for attr, value in (
                (ATTR_VOC, self.volatile_organic_compounds),
                (ATTR_AQI_LEVEL, self.air_quality_index_level),
                (ATTR_AQI_POLLUTANT, self.air_quality_index_pollutant),
            )
            if value is not None
        }

    async def async_added_to_hass(self):
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_KAITERRA, self.async_write_ha_state
            )
        )
