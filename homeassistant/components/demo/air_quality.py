"""Demo platform that offers fake air quality data."""
from __future__ import annotations

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [DemoAirQuality("Home", 14, 23, 100), DemoAirQuality("Office", 4, 16, None)]
    )


class DemoAirQuality(AirQualityEntity):
    """Representation of Air Quality data."""

    _attr_attribution = "Powered by Home Assistant"
    _attr_should_poll = False

    def __init__(self, name: str, pm_2_5: int, pm_10: int, n2o: int | None) -> None:
        """Initialize the Demo Air Quality."""
        self._attr_name = f"Demo Air Quality {name}"
        self._pm_2_5 = pm_2_5
        self._pm_10 = pm_10
        self._n2o = n2o

    @property
    def particulate_matter_2_5(self) -> int:
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    def particulate_matter_10(self) -> int:
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    def nitrogen_oxide(self) -> int | None:
        """Return the nitrogen oxide (N2O) level."""
        return self._n2o
