"""Integration with the Rachio Iro sprinkler system controller."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN as DOMAIN_RACHIO,
    KEY_BATTERY,
    KEY_DETECT_FLOW,
    KEY_DEVICE_ID,
    KEY_FLOW,
    KEY_ONLINE,
    KEY_RAIN_SENSOR,
    KEY_RAIN_SENSOR_TRIPPED,
    KEY_STATUS,
    KEY_SUBTYPE,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_RAIN_SENSOR_UPDATE,
    STATUS_ONLINE,
)
from .coordinator import RachioUpdateCoordinator
from .device import RachioIro, RachioPerson
from .entity import RachioDevice, RachioHoseTimerEntity
from .webhooks import (
    SUBTYPE_COLD_REBOOT,
    SUBTYPE_OFFLINE,
    SUBTYPE_ONLINE,
    SUBTYPE_RAIN_SENSOR_DETECTION_OFF,
    SUBTYPE_RAIN_SENSOR_DETECTION_ON,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RachioControllerBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Rachio controller binary sensor."""

    update_received: Callable[[str], bool | None]
    is_on: Callable[[RachioIro], bool]
    signal_string: str


CONTROLLER_BINARY_SENSOR_TYPES: tuple[RachioControllerBinarySensorDescription, ...] = (
    RachioControllerBinarySensorDescription(
        key=KEY_ONLINE,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        signal_string=SIGNAL_RACHIO_CONTROLLER_UPDATE,
        is_on=lambda controller: controller.init_data[KEY_STATUS] == STATUS_ONLINE,
        update_received=lambda state: (
            True
            if state in (SUBTYPE_ONLINE, SUBTYPE_COLD_REBOOT)
            else False
            if state == SUBTYPE_OFFLINE
            else None
        ),
    ),
    RachioControllerBinarySensorDescription(
        key=KEY_RAIN_SENSOR,
        translation_key="rain",
        device_class=BinarySensorDeviceClass.MOISTURE,
        signal_string=SIGNAL_RACHIO_RAIN_SENSOR_UPDATE,
        is_on=lambda controller: controller.init_data[KEY_RAIN_SENSOR_TRIPPED],
        update_received=lambda state: (
            True
            if state == SUBTYPE_RAIN_SENSOR_DETECTION_ON
            else False
            if state == SUBTYPE_RAIN_SENSOR_DETECTION_OFF
            else None
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class RachioHoseTimerBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Rachio hose timer binary sensor."""

    value_fn: Callable[[RachioHoseTimerEntity], bool]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _: True


HOSE_TIMER_BINARY_SENSOR_TYPES: tuple[RachioHoseTimerBinarySensorDescription, ...] = (
    RachioHoseTimerBinarySensorDescription(
        key=KEY_BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda device: device.battery,
    ),
    RachioHoseTimerBinarySensorDescription(
        key=KEY_FLOW,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="flow",
        value_fn=lambda device: device.no_flow_detected,
        exists_fn=lambda valve: valve[KEY_DETECT_FLOW],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Rachio binary sensors."""
    entities = await hass.async_add_executor_job(_create_entities, hass, config_entry)
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config_entry: ConfigEntry) -> list[Entity]:
    entities: list[Entity] = []
    person: RachioPerson = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
    entities.extend(
        RachioControllerBinarySensor(controller, description)
        for controller in person.controllers
        for description in CONTROLLER_BINARY_SENSOR_TYPES
    )
    entities.extend(
        RachioHoseTimerBinarySensor(valve, base_station.status_coordinator, description)
        for base_station in person.base_stations
        for valve in base_station.status_coordinator.data.values()
        for description in HOSE_TIMER_BINARY_SENSOR_TYPES
        if description.exists_fn(valve)
    )
    return entities


class RachioControllerBinarySensor(RachioDevice, BinarySensorEntity):
    """Represent a binary sensor that reflects a Rachio controller state."""

    entity_description: RachioControllerBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        controller: RachioIro,
        description: RachioControllerBinarySensorDescription,
    ) -> None:
        """Initialize a controller binary sensor."""
        super().__init__(controller)
        self.entity_description = description
        self._attr_unique_id = f"{controller.controller_id}-{description.key}"

    @callback
    def _async_handle_any_update(self, *args, **kwargs) -> None:
        """Determine whether an update event applies to this device."""
        if args[0][KEY_DEVICE_ID] != self._controller.controller_id:
            # For another device
            return

        # For this device
        self._async_handle_update(args, kwargs)

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle an update to the state of this sensor."""
        updated_state = self.entity_description.update_received(args[0][0][KEY_SUBTYPE])
        if updated_state is not None:
            self._attr_is_on = updated_state

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._attr_is_on = self.entity_description.is_on(self._controller)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.entity_description.signal_string,
                self._async_handle_any_update,
            )
        )


class RachioHoseTimerBinarySensor(RachioHoseTimerEntity, BinarySensorEntity):
    """Represents a binary sensor for a smart hose timer."""

    entity_description: RachioHoseTimerBinarySensorDescription

    def __init__(
        self,
        data: dict[str, Any],
        coordinator: RachioUpdateCoordinator,
        description: RachioHoseTimerBinarySensorDescription,
    ) -> None:
        """Initialize a smart hose timer binary sensor."""
        super().__init__(data, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.id}-{description.key}"
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Handle updated coordinator data."""
        self._attr_is_on = self.entity_description.value_fn(self)
