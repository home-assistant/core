"""Base auto-entity class."""

from functools import cached_property
from typing import Generic, TypeVar, cast

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .auto_area import AutoArea
from .calculations import get_calculation

_TEntity = TypeVar("_TEntity", bound=Entity)
_TDeviceClass = TypeVar(
    "_TDeviceClass", BinarySensorDeviceClass, SensorDeviceClass, CoverDeviceClass
)

import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AutoEntity(Entity, Generic[_TEntity, _TDeviceClass]):
    """Set up an Auto Area entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        auto_area: AutoArea,
        device_class: _TDeviceClass,
        name_prefix: str,
        prefix: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__()
        self.hass = hass
        self.auto_area = auto_area
        self._device_class = device_class
        self._name_prefix = name_prefix
        self._prefix = prefix

        self.entity_ids: list[str] = self._get_sensor_entities()
        self.unsubscribe = None
        self.entity_states: dict[str, State] = {}
        self._aggregated_state: StateType = None

        _LOGGER.info(
            "%s (%s): Initialized sensor. Entities: %s",
            self.auto_area.area_name,
            self.device_class,
            self.entity_ids,
        )

    def _get_sensor_entities(self) -> list[str]:
        """Retrieve all relevant entity ids for this sensor."""
        return [
            entity.entity_id
            for entity in self.auto_area.get_valid_entities()
            if entity.device_class == self.device_class
            or entity.original_device_class == self.device_class
        ]

    @cached_property
    def name(self):
        """Name of this entity."""
        return f"{self._name_prefix}{self.auto_area.area_name}"

    @cached_property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.auto_area.area_id}_aggregated_{self.device_class}"

    @cached_property
    def device_class(self) -> _TDeviceClass:
        """Return device class."""
        return cast(_TDeviceClass, self._device_class)

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @cached_property
    def suggested_display_precision(self) -> int | None:
        """Set the suggested precision (0.12)."""
        return 2

    async def async_added_to_hass(self):
        """Start tracking sensors."""
        # Get all current states
        for entity_id in self.entity_ids:
            state = self.hass.states.get(entity_id)
            if state is not None:
                try:
                    self.entity_states[entity_id] = state
                except ValueError:
                    _LOGGER.warning(
                        "%s (%s): No initial state available for %s",
                        self.auto_area.area_name,
                        self.device_class,
                        entity_id,
                    )

        self._aggregated_state = self._get_state()
        self.schedule_update_ha_state()

        # Subscribe to state changes
        self.unsubscribe = async_track_state_change_event(
            self.hass,
            self.entity_ids,
            self._handle_state_change,
        )

    async def _handle_state_change(self, event: Event[EventStateChangedData]):
        """Handle state change of any tracked illuminance sensors."""
        to_state = event.data.get("new_state")
        if to_state is None:
            return

        if to_state.state in [
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ]:
            self.entity_states.pop(to_state.entity_id, None)
        else:
            try:
                to_state.state = float(to_state.state)  # type: ignore
                self.entity_states[to_state.entity_id] = to_state
            except ValueError:
                self.entity_states.pop(to_state.entity_id, None)

        self._aggregated_state = self._get_state()

        self.async_schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up event listeners."""
        if self.unsubscribe:
            self.unsubscribe()

    def _get_state(self) -> StateType | None:
        """Get the state of the sensor."""
        calculate_state = get_calculation(self.device_class)

        if calculate_state is None:
            _LOGGER.error(
                "%s: %s unable to get state calculation method",
                self.auto_area.area_name,
                self.device_class,
            )
            return None

        return calculate_state(list(self.entity_states.values()))
