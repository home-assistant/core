"""Support for IPP sensors."""
from typing import Any, Callable, Dict, List, Optional, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import IPPDataUpdateCoordinator, IPPDeviceEntity
from .const import (
    ATTR_MARKER_HIGH_LEVEL,
    ATTR_MARKER_LOW_LEVEL,
    ATTR_MARKER_TYPE,
    ATTR_PRINTER_COMMAND_SET,
    ATTR_PRINTER_INFO,
    ATTR_PRINTER_LOCATION,
    ATTR_PRINTER_SERIAL,
    ATTR_PRINTER_STATE_MESSAGE,
    ATTR_PRINTER_STATE_REASON,
    ATTR_PRINTER_URI_SUPPORTED,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up IPP sensor based on a config entry."""
    coordinator: IPPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    sensors.append(IPPPrinterSensor(entry.entry_id, coordinator))

    for marker_index in range(len(coordinator.data.markers)):
        sensors.append(IPPMarkerSensor(entry.entry_id, coordinator, marker_index))

    async_add_entities(sensors, True)


class IPPSensor(IPPDeviceEntity):
    """Defines an IPP sensor."""

    def __init__(
        self,
        *,
        coordinator: IPPDataUpdateCoordinator,
        enabled_default: bool = True,
        entry_id: str,
        icon: str,
        key: str,
        name: str,
        unit_of_measurement: Optional[str] = None,
    ) -> None:
        """Initialize IPP sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._key = key

        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            enabled_default=enabled_default,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.data.info.uuid}_{self._key}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class IPPMarkerSensor(IPPSensor):
    """Defines an IPP marker sensor."""

    def __init__(
        self, entry_id: str, coordinator: IPPDataUpdateCoordinator, marker_index: int
    ) -> None:
        """Initialize IPP marker sensor."""
        self.marker_index = marker_index

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:water",
            key=f"marker_{marker_index}",
            name=f"{coordinator.data.info.name} {coordinator.data.markers[marker_index].name}",
            unit_of_measurement=UNIT_PERCENTAGE,
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {
            ATTR_MARKER_HIGH_LEVEL: self.coordinator.data.markers[
                self.marker_index
            ].high_level,
            ATTR_MARKER_LOW_LEVEL: self.coordinator.data.markers[
                self.marker_index
            ].low_level,
            ATTR_MARKER_TYPE: self.coordinator.data.markers[
                self.marker_index
            ].marker_type,
        }

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return self.coordinator.data.markers[self.marker_index].level


class IPPPrinterSensor(IPPSensor):
    """Defines an IPP printer sensor."""

    def __init__(self, entry_id: str, coordinator: IPPDataUpdateCoordinator) -> None:
        """Initialize IPP printer sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:printer",
            key="printer",
            name=coordinator.data.info.name,
            unit_of_measurement=None,
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {
            ATTR_PRINTER_INFO: self.coordinator.data.info.printer_info,
            ATTR_PRINTER_SERIAL: self.coordinator.data.info.serial,
            ATTR_PRINTER_LOCATION: self.coordinator.data.info.location,
            ATTR_PRINTER_STATE_MESSAGE: self.coordinator.data.state.message,
            ATTR_PRINTER_STATE_REASON: self.coordinator.data.state.reasons,
            ATTR_PRINTER_COMMAND_SET: self.coordinator.data.info.command_set,
            ATTR_PRINTER_URI_SUPPORTED: self.coordinator.data.info.printer_uri_supported,
        }

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return self.coordinator.data.state.printer_state
