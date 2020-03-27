"""Support for the GIOS service."""
from homeassistant.components.air_quality import (
    ATTR_CO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
    AirQualityEntity,
)
from homeassistant.const import CONF_NAME

from .const import ATTR_STATION, DOMAIN, ICONS_MAP

ATTRIBUTION = "Data provided by GIOŚ"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a GIOS entities from a config_entry."""
    name = config_entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([GiosAirQuality(coordinator, name)], False)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class GiosAirQuality(AirQualityEntity):
    """Define an GIOS sensor."""

    def __init__(self, coordinator, name):
        """Initialize."""
        self.coordinator = coordinator
        self._name = name
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        if self.air_quality_index in ICONS_MAP:
            return ICONS_MAP[self.air_quality_index]
        return "mdi:blur"

    @property
    def air_quality_index(self):
        """Return the air quality index."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["AQI"]["value"]
            if "AQI" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["PM2.5"]["value"]
            if "PM2.5" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["PM10"]["value"]
            if "PM10" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def ozone(self):
        """Return the O3 (ozone) level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["O3"]["value"]
            if "O3" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["CO"]["value"]
            if "CO" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["SO2"]["value"]
            if "SO2" in self.coordinator.data
            else None
        )

    @property
    @round_state
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        return (
            self.coordinator.data["NO2"]["value"]
            if "NO2" in self.coordinator.data
            else None
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self.coordinator.gios.station_id

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        # Different measuring stations have different sets of sensors. We don't know
        # what data we will get.
        if "CO" in self.coordinator.data:
            self._attrs[f"{ATTR_CO}_index"] = self.coordinator.data["CO"]["index"]
        if "NO2" in self.coordinator.data:
            self._attrs[f"{ATTR_NO2}_index"] = self.coordinator.data["NO2"]["index"]
        if "O3" in self.coordinator.data:
            self._attrs[f"{ATTR_OZONE}_index"] = self.coordinator.data["O3"]["index"]
        if "PM2.5" in self.coordinator.data:
            self._attrs[f"{ATTR_PM_2_5}_index"] = self.coordinator.data["PM2.5"][
                "index"
            ]
        if "PM10" in self.coordinator.data:
            self._attrs[f"{ATTR_PM_10}_index"] = self.coordinator.data["PM10"]["index"]
        if "SO2" in self.coordinator.data:
            self._attrs[f"{ATTR_SO2}_index"] = self.coordinator.data["SO2"]["index"]
        self._attrs[ATTR_STATION] = self.coordinator.gios.station_name
        return self._attrs

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Update GIOS entity."""
        await self.coordinator.async_request_refresh()
