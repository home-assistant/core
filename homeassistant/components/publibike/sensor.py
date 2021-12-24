"""Support for PubliBike Public API for bike sharing in Switzerland."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY_LIMIT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PubliBike sensors."""
    station = hass.data[DOMAIN][config_entry.entry_id]["station"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    battery_limit = hass.data[DOMAIN][config_entry.entry_id][BATTERY_LIMIT]
    entities = [
        EBikeSensor(station, coordinator, battery_limit),
        BikeSensor(station, coordinator),
    ]

    async_add_entities(entities)


class PubliBikeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a PubliBike sensor."""

    def __init__(self, station, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.station = station
        self.coordinator = coordinator
        self.attributes = {}
        self.bike_type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.station.name} - {self.bike_type.capitalize()}s"

    def refresh_common_attributes(self):
        """Update attributes dictionary."""
        self.attributes.update(
            {
                "Station name": self.station.name,
                "Station ID": self.station.stationId,
            }
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self.refresh_common_attributes()
        return self.attributes


class EBikeSensor(PubliBikeSensor):
    """Representation of an E-Bike Sensor."""

    def __init__(self, station, coordinator, battery_limit=None):
        """Initialize the sensor."""
        super().__init__(station, coordinator)
        self.bike_type = "E-bike"
        self.battery_limit = battery_limit

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self.battery_limit:
            return len(
                [
                    bike
                    for bike in self.station.ebikes
                    if bike.batteryLevel >= self.battery_limit
                ]
            )
        return len(self.station.ebikes)

    def get_battery_levels(self):
        """Update battery level for every bike."""
        return {f"Bike {bike.name}": bike.batteryLevel for bike in self.station.ebikes}

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self.refresh_common_attributes()
        self.attributes.update({"All E-bikes": len(self.station.ebikes)})

        batteries = self.get_battery_levels()
        self.attributes = {
            k: v for k, v in self.attributes.items() if not k.startswith("Bike ")
        }
        self.attributes.update(batteries)
        return self.attributes


class BikeSensor(PubliBikeSensor):
    """Representation of a Bike Sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the sensor."""
        super().__init__(*args, **kwargs)
        self.bike_type = "bike"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self.station.bikes)
