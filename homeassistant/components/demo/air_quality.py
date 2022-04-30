"""Demo platform that offers fake air quality data."""
from __future__ import annotations

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Air Quality."""
    async_add_entities(
        [DemoAirQuality("Home", 14, 23, 100), DemoAirQuality("Office", 4, 16, None)]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoAirQuality(AirQualityEntity):
    """Representation of Air Quality data."""

    def __init__(self, name, pm_2_5, pm_10, n2o):
        """Initialize the Demo Air Quality."""
        self._name = name
        self._pm_2_5 = pm_2_5
        self._pm_10 = pm_10
        self._n2o = n2o

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Demo Air Quality {self._name}"

    @property
    def should_poll(self):
        """No polling needed for Demo Air Quality."""
        return False

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    def nitrogen_oxide(self):
        """Return the nitrogen oxide (N2O) level."""
        return self._n2o

    @property
    def attribution(self):
        """Return the attribution."""
        return "Powered by Home Assistant"
