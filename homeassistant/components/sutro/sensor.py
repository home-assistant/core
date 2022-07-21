"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sutro_api import SutroApi


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sutro sensor entities."""
    sutro_api: SutroApi = hass.data[DOMAIN]

    info = await sutro_api.async_get_info()
    async_add_entities(
        [
            AciditySensor(sutro_api, info),
            AlkalinitySensor(sutro_api, info),
            FreeChlorineSensor(sutro_api, info),
            TemperatureSensor(sutro_api, info),
        ]
    )


class AciditySensor(SensorEntity):
    """Representation of an Acidity Sensor."""

    _attr_name = "Acidity"
    _attr_icon = "mdi:ph"
    _attr_native_unit_of_measurement = "pH"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, api, info):
        """Initialize Acidity Sensor."""
        self._api = api
        self._attr_unique_id = f"{info['data']['me']['device']['serialNumber']}_acidity"
        self._attr_native_value = float(
            info["data"]["me"]["pool"]["latestReading"]["ph"]
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        info = await self._api.async_get_info()
        self._attr_native_value = float(
            info["data"]["me"]["pool"]["latestReading"]["ph"]
        )


class AlkalinitySensor(SensorEntity):
    """Representation of an Alkalinity Sensor."""

    _attr_name = "Alkalinity"
    _attr_icon = "mdi:test-tube"
    _attr_native_unit_of_measurement = "mg/L CaC03"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, api, info):
        """Initialize Alkalinity Sensor."""
        self._api = api
        self._attr_unique_id = (
            f"{info['data']['me']['device']['serialNumber']}_alkalinity"
        )
        self._attr_native_value = float(
            info["data"]["me"]["pool"]["latestReading"]["alkalinity"]
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        info = await self._api.async_get_info()
        self._attr_native_value = info["data"]["me"]["pool"]["latestReading"][
            "alkalinity"
        ]


class FreeChlorineSensor(SensorEntity):
    """Representation of a Free Chlorine Sensor."""

    _attr_name = "Free Chlorine"
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, api, info):
        """Initialize Free Chlorine Sensor."""
        self._api = api
        self._attr_unique_id = (
            f"{info['data']['me']['device']['serialNumber']}_chlorine"
        )
        self._attr_native_value = float(
            info["data"]["me"]["pool"]["latestReading"]["chlorine"]
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        info = await self._api.async_get_info()
        self._attr_native_value = float(
            info["data"]["me"]["pool"]["latestReading"]["chlorine"]
        )


class TemperatureSensor(SensorEntity):
    """Representation of a Temperature Sensor."""

    _attr_name = "Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = TEMP_FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, api, info):
        """Initialize Temperature Sensor."""
        self._api = api
        self._attr_unique_id = (
            f"{info['data']['me']['device']['serialNumber']}_temperature"
        )
        self._attr_native_value = float(info["data"]["me"]["device"]["temperature"])

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        info = await self._api.async_get_info()
        self._attr_native_value = float(info["data"]["me"]["device"]["temperature"])
