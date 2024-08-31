"""Binary sensor platform for hvv_departures."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectorError
from pygti.exceptions import InvalidAuth

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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
                    name = f"Elevator {label}"
                else:
                    name = "Unknown elevator"

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
                    },
                }
        return elevators

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        payload = {"station": {"id": station["id"], "type": station["type"]}}

        try:
            async with asyncio.timeout(10):
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

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, idx, config_entry):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.idx = idx

        self._attr_name = coordinator.data[idx]["name"]
        self._attr_unique_id = idx
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    config_entry.entry_id,
                    config_entry.data[CONF_STATION]["id"],
                    config_entry.data[CONF_STATION]["type"],
                )
            },
            manufacturer=MANUFACTURER,
            name=f"Departures at {config_entry.data[CONF_STATION]['name']}",
        )

    @property
    def is_on(self):
        """Return entity state."""
        return self.coordinator.data[self.idx]["state"]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data[self.idx]["available"]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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
