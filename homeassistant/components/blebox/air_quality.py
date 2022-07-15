"""BleBox air quality entity."""
from datetime import timedelta

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox air quality entity."""
    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxAirQualityEntity, "air_qualities"
    )


class BleBoxAirQualityEntity(BleBoxEntity, AirQualityEntity):
    """Representation of a BleBox air quality feature."""

    _attr_icon = "mdi:blur"

    @property
    def particulate_matter_0_1(self):
        """Return the particulate matter 0.1 level."""
        return self._feature.pm1

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._feature.pm2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._feature.pm10
