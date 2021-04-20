"""BleBox air quality entity."""

from homeassistant.components.air_quality import AirQualityEntity

from . import BleBoxEntity, create_blebox_entities


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a BleBox air quality entity."""
    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxAirQualityEntity, "air_qualities"
    )


class BleBoxAirQualityEntity(BleBoxEntity, AirQualityEntity):
    """Representation of a BleBox air quality feature."""

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:blur"

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
