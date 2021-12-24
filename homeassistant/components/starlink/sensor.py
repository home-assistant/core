"""Sensor entities for the Starlink dish."""

from spacex.starlink import DishAlert

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_RATE_MEGABITS_PER_SECOND,
    DEGREE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    TIME_MILLISECONDS,
)
from homeassistant.core import HomeAssistant

from . import BaseStarlinkEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the sensor entities of Starlink."""
    dish, coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [entity(coordinator, dish) for entity in StarlinkSensorEntity.__subclasses__()]
    )

    return True


class StarlinkSensorEntity(BaseStarlinkEntity, SensorEntity):
    """Parent class of all Sensor entities."""

    @property
    def state_class(self):
        """Return the state class for this entity."""
        return "measurement"


class PingDropRate(StarlinkSensorEntity):
    """The percent of pings dropped, as reported by the satellite."""

    base_name = "Ping Drop Rate"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return PERCENTAGE

    @property
    def unique_id(self):
        """Return the unique ID for the entity."""
        return f"{self.dish.id}.drop_rate"

    @property
    def icon(self):
        """Return an icon representing the entity, and whether any pings are being dropped."""
        if self.state > 0:
            return "mdi:close-network"
        else:
            return "mdi:check-network"

    @property
    def entity_category(self):
        """Return the category for the entity."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def state(self):
        """Return the percentage of pings being dropped as reported by the satellite."""
        return round(self.dish.status.ping_drop_rate * 100.0, 2)


class PingLatency(StarlinkSensorEntity):
    """The average time for a ping to complete, as reported by the satellite."""

    base_name = "Ping Latency"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return TIME_MILLISECONDS

    @property
    def unique_id(self):
        """Return the unique ID for the entity."""
        return f"{self.dish.id}.ping_latency"

    @property
    def icon(self):
        """Return an icon representing the entity."""
        return "mdi:timeline-clock"

    @property
    def entity_category(self):
        """Return the category for the entity."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def state(self):
        """Return the ping latency, in milliseconds."""
        return round(self.dish.status.ping_latency, 3)


class DownlinkThroughput(StarlinkSensorEntity):
    """The volume of data being downloaded by the satellite."""

    base_name = "Downlink Throughput"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return DATA_RATE_MEGABITS_PER_SECOND

    @property
    def icon(self):
        """Return an icon for the entity."""
        return "mdi:download"

    @property
    def unique_id(self):
        """Return a unique ID for the entity."""
        return f"{self.dish.id}.downlink_throughput"

    @property
    def state(self):
        """Return the volume of data downloaded by the dish."""
        return round(self.dish.status.downlink_throughput / (1000 ** 2), 3)


class UplinkThroughput(StarlinkSensorEntity):
    """The volume of data being uploaded by the satellite."""

    base_name = "Uplink Throughput"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return DATA_RATE_MEGABITS_PER_SECOND

    @property
    def icon(self):
        """Return an icon for the entity."""
        return "mdi:upload"

    @property
    def unique_id(self):
        """Return a unique ID for the entity."""
        return f"{self.dish.id}.uplink_throughput"

    @property
    def state(self):
        """Return the volume of data uploaded by the dish."""
        return round(self.dish.status.uplink_throughput / (1000 ** 2), 3)


class Azimuth(StarlinkSensorEntity):
    """The angle of the satellite, pointing horizontally."""

    base_name = "Azimuth"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return DEGREE

    @property
    def icon(self):
        """Return an icon for the entity."""
        return "mdi:axis-z-rotate-clockwise"

    @property
    def unique_id(self):
        """Return a unique ID for the entity."""
        return f"{self.dish.id}.azimuth"

    @property
    def entity_category(self):
        """Return the category for the entity."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def state(self):
        """Return the angle of the dish horizontally."""
        return round(self.dish.status.azimuth_deg, 2)

    @property
    def state_class(self):
        """Return the state class, which is None for device positioning metrics."""
        return None


class Elevation(StarlinkSensorEntity):
    """The angle of the satellite, pointing horizontally."""

    base_name = "Elevation"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the entity."""
        return DEGREE

    @property
    def icon(self):
        """Return an icon for the entity."""
        return "mdi:angle-acute"

    @property
    def unique_id(self):
        """Return a unique ID for the entity."""
        return f"{self.dish.id}.elevation"

    @property
    def entity_category(self):
        """Return the category for the entity."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def state(self):
        """Return the angle of the dish horizontally."""
        return round(self.dish.status.elevation_deg, 2)

    @property
    def state_class(self):
        """Return the state class, which is None for device positioning metrics."""
        return None


class NumberOfAlerts(StarlinkSensorEntity):
    """The number of alerts being reported by the satellite."""

    base_name = "Number of Alerts"

    @property
    def unique_id(self):
        """Return a unique ID for the entity."""
        return f"{self.dish.id}.alerts"

    @property
    def icon(self):
        """Return an icon for the entity, representing whether there are any alerts."""
        if self.state == 0:
            return "mdi:check-circle"
        else:
            return "mdi:alert"

    @property
    def state(self):
        """Return the number of alerts."""
        return len(self.dish.status.alerts)

    @property
    def entity_category(self):
        """Return the category for the entity."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def state_attributes(self):
        """Return a mapping of each of the possible alerts to whether or not its active."""
        return {alert.label: alert in self.dish.status.alerts for alert in DishAlert}
