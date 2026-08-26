"""Binary sensor platform for hvv_departures."""

import asyncio
from datetime import timedelta
import logging
from typing import Any, override

from aiohttp import ClientConnectorError
from pygti.exceptions import GTIError
from pygti.models import (
    ElevatorState,
    SDName,
    SDNameType,
    StationInformationRequest,
    StationInformationResponse,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTRIBUTION, CONF_STATION, DOMAIN, MANUFACTURER
from .hub import HVVConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HVVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    hub = entry.runtime_data
    station_name = entry.data[CONF_STATION]["name"]
    station = entry.data[CONF_STATION]

    def get_elevator_entities_from_station_information(
        station_name: str,
        station_information: StationInformationResponse | None,
    ) -> dict[str, Any]:
        """Convert station information into a list of elevators."""
        elevators = {}

        if station_information is None:
            return {}

        for partial_station in station_information.partialStations or []:
            for elevator in partial_station.elevators or []:
                state = elevator.state != ElevatorState.READY
                available = elevator.state != ElevatorState.UNKNOWN
                label = elevator.label
                description = elevator.description

                if label is not None:
                    name = f"Elevator {label}"
                else:
                    name = "Unknown elevator"

                if description is not None:
                    name += f" ({description})"

                lines = elevator.lines

                idx = f"{station_name}-{label}-{lines}"

                elevators[idx] = {
                    "state": state,
                    "name": name,
                    "available": available,
                    "attributes": {
                        "cabin_width": elevator.cabinWidth,
                        "cabin_length": elevator.cabinLength,
                        "door_width": elevator.doorWidth,
                        "elevator_type": elevator.elevatorType,
                        "button_type": elevator.buttonType,
                        "cause": elevator.cause,
                        "lines": lines,
                    },
                }
        return elevators

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        payload = StationInformationRequest(
            station=SDName(id=station["id"], type=SDNameType(station["type"]))
        )

        try:
            async with asyncio.timeout(10):
                return get_elevator_entities_from_station_information(
                    station_name, await hub.gti.getStationInformation(payload)
                )
        except GTIError as err:
            raise UpdateFailed(f"GTI API error: {err}") from err
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
        config_entry=entry,
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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        idx: str,
        config_entry: HVVConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.idx = idx

        self._attr_name = coordinator.data[idx]["name"]
        self._attr_unique_id = idx
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (  # type: ignore[arg-type]
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
    @override
    def is_on(self) -> bool:
        """Return entity state."""
        return bool(self.coordinator.data[self.idx]["state"])

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data[self.idx]["available"]
        )

    @property
    @override
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
