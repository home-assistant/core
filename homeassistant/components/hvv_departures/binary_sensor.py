"""Binary sensor platform for hvv_departures."""
from datetime import timedelta
import logging

from aiohttp import ClientConnectorError
import async_timeout
from pygti.exceptions import InvalidAuth

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTRIBUTION, CONF_STATION, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary_sensor platform."""
    hub = hass.data[DOMAIN][entry.entry_id]
    station_name = entry.data[CONF_STATION]["name"]
    station = entry.data[CONF_STATION]

    def get_elevator_entities_from_station_information(
        station_name, station_information
    ):
        """Convert station information into a list of elevators."""
        elevators = {}

        if station_information is None:
            return {}

        for partial_station in station_information.get("partialStations", []):
            for elevator in partial_station.get("elevators", []):

                state = elevator.get("state") != "READY"
                available = elevator.get("state") != "UNKNOWN"
                label = elevator.get("label")
                description = elevator.get("description")

                if label is not None:
                    name = f"Elevator {label} at {station_name}"
                else:
                    name = f"Unknown elevator at {station_name}"

                if description is not None:
                    name += f" ({description})"

                lines = elevator.get("lines")

                idx = f"{station_name}-{label}-{lines}"

                elevators[idx] = {
                    "state": state,
                    "name": name,
                    "available": available,
                    "attributes": {
                        "cabin_width": elevator.get("cabinWidth"),
                        "cabin_length": elevator.get("cabinLength"),
                        "door_width": elevator.get("doorWidth"),
                        "elevator_type": elevator.get("elevatorType"),
                        "button_type": elevator.get("buttonType"),
                        "cause": elevator.get("cause"),
                        "lines": lines,
                        ATTR_ATTRIBUTION: ATTRIBUTION,
                    },
                }
        return elevators

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        payload = {"station": station}

        try:
            async with async_timeout.timeout(10):
                return get_elevator_entities_from_station_information(
                    station_name, await hub.gti.stationInformation(payload)
                )
        except InvalidAuth as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ClientConnectorError as err:
            raise UpdateFailed(f"Network not available: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error occurred while fetching data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="hvv_departures.binary_sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(hours=1),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities(
        HvvDepartureBinarySensor(coordinator, idx, entry)
        for (idx, ent) in coordinator.data.items()
    )


class HvvDepartureBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """HVVDepartureBinarySensor class."""

    def __init__(self, coordinator, idx, config_entry):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.idx = idx
        self.config_entry = config_entry

    @property
    def is_on(self):
        """Return entity state."""
        return self.coordinator.data[self.idx]["state"]

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data[self.idx]["available"]
        )

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.config_entry.entry_id,
                    self.config_entry.data[CONF_STATION]["id"],
                    self.config_entry.data[CONF_STATION]["type"],
                )
            },
            manufacturer=MANUFACTURER,
            name=f"Departures at {self.config_entry.data[CONF_STATION]['name']}",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.coordinator.data[self.idx]["name"]

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return self.idx

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.PROBLEM

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not (
            self.coordinator.last_update_success
            and self.coordinator.data[self.idx]["available"]
        ):
            return None
        return {
            k: v
            for k, v in self.coordinator.data[self.idx]["attributes"].items()
            if v is not None
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
