"""Support for Tado sensors for each zone."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    TYPE_AIR_CONDITIONING,
    TYPE_BATTERY,
    TYPE_HEATING,
    TYPE_HOT_WATER,
    TYPE_POWER,
    TADO_LINE_X,
    TADO_PRE_LINE_X,
)
from .coordinator import TadoConfigEntry, TadoDataUpdateCoordinator
from .entity import TadoDeviceEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TadoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Tado binary sensor entity."""

    state_fn: Callable[[Any], bool]

    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None


BATTERY_STATE_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="battery state",
    state_fn=lambda data: data["batteryState"] == "LOW",
    device_class=BinarySensorDeviceClass.BATTERY,
)
CONNECTION_STATE_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="connection state",
    translation_key="connection_state",
    state_fn=lambda data: data.get("connectionState", {}).get("value", False),
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
TADO_X_CONNECTION_STATE_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="connection state",
    translation_key="connection_state",
    state_fn=lambda data: data.get("connection", {}).get("state", False),
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
POWER_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="power",
    state_fn=lambda data: data.power == "ON",
    device_class=BinarySensorDeviceClass.POWER,
)
LINK_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="link",
    state_fn=lambda data: data.link in ("ONLINE", "CONNECTED"),
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
OVERLAY_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="overlay",
    translation_key="overlay",
    state_fn=lambda data: data.overlay_active,
    attributes_fn=lambda data: (
        {"termination": data.overlay_termination_type} if data.overlay_active else {}
    ),
    device_class=BinarySensorDeviceClass.POWER,
)
OPEN_WINDOW_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="open window",
    state_fn=lambda data: bool(data.open_window or data.open_window_detected),
    attributes_fn=lambda data: data.open_window_attr,
    device_class=BinarySensorDeviceClass.WINDOW,
)
EARLY_START_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="early start",
    translation_key="early_start",
    state_fn=lambda data: data.preparation,
    device_class=BinarySensorDeviceClass.POWER,
)

DEVICE_SENSORS = {
    TADO_LINE_X: {
        TYPE_BATTERY: [
            BATTERY_STATE_ENTITY_DESCRIPTION,
            TADO_X_CONNECTION_STATE_ENTITY_DESCRIPTION,
        ],
        TYPE_POWER: [
            TADO_X_CONNECTION_STATE_ENTITY_DESCRIPTION,
        ],
    },
    TADO_PRE_LINE_X: {
        TYPE_BATTERY: [
            BATTERY_STATE_ENTITY_DESCRIPTION,
            CONNECTION_STATE_ENTITY_DESCRIPTION,
        ],
        TYPE_POWER: [
            CONNECTION_STATE_ENTITY_DESCRIPTION,
        ],
    },
}

ZONE_SENSORS = {
    TADO_LINE_X: {
        TYPE_HEATING: [
            POWER_ENTITY_DESCRIPTION,
            LINK_ENTITY_DESCRIPTION,
            OVERLAY_ENTITY_DESCRIPTION,
            OPEN_WINDOW_ENTITY_DESCRIPTION,
        ],
        TYPE_HOT_WATER: [
            POWER_ENTITY_DESCRIPTION,
            LINK_ENTITY_DESCRIPTION,
            OVERLAY_ENTITY_DESCRIPTION,
        ],
    },
    TADO_PRE_LINE_X: {
        TYPE_HEATING: [
            POWER_ENTITY_DESCRIPTION,
            LINK_ENTITY_DESCRIPTION,
            OVERLAY_ENTITY_DESCRIPTION,
            OPEN_WINDOW_ENTITY_DESCRIPTION,
            EARLY_START_ENTITY_DESCRIPTION,
        ],
        TYPE_AIR_CONDITIONING: [
            POWER_ENTITY_DESCRIPTION,
            LINK_ENTITY_DESCRIPTION,
            OVERLAY_ENTITY_DESCRIPTION,
            OPEN_WINDOW_ENTITY_DESCRIPTION,
        ],
        TYPE_HOT_WATER: [
            POWER_ENTITY_DESCRIPTION,
            LINK_ENTITY_DESCRIPTION,
            OVERLAY_ENTITY_DESCRIPTION,
        ],
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado sensor platform."""

    tado = entry.runtime_data
    devices = tado.devices
    zones = tado.zones
    entities: list[BinarySensorEntity] = []

    tado_line = TADO_LINE_X if tado.is_x else TADO_PRE_LINE_X

    # Create device sensors
    for device in devices:
        if "batteryState" in device:
            device_type = TYPE_BATTERY
        else:
            device_type = TYPE_POWER

        entities.extend(
            [
                TadoDeviceBinarySensor(tado, device, entity_description)
                for entity_description in DEVICE_SENSORS[tado_line][device_type]
            ]
        )

    # Create zone sensors
    for zone in zones:
        zone_type = zone["type"]
        if zone_type not in ZONE_SENSORS[tado_line]:
            _LOGGER.warning(
                "Unknown or unsupported zone type skipped: %s, tado line: %s",
                zone_type,
                tado_line,
            )
            continue

        entities.extend(
            [
                TadoZoneBinarySensor(tado, zone["name"], zone["id"], entity_description)
                for entity_description in ZONE_SENSORS[tado_line][zone_type]
            ]
        )

    async_add_entities(entities, True)


class TadoDeviceBinarySensor(TadoDeviceEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        device_info: dict[str, Any],
        entity_description: TadoBinarySensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator)

        self._attr_unique_id = (
            f"{entity_description.key} {self.device_id} {coordinator.home_id}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._device_info = self.coordinator.data["device"][self.device_id]
        except KeyError:
            return

        self._attr_is_on = self.entity_description.state_fn(self._device_info)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._device_info
            )
        super()._handle_coordinator_update()


class TadoZoneBinarySensor(TadoZoneEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
        entity_description: TadoBinarySensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._attr_unique_id = (
            f"{entity_description.key} {zone_id} {coordinator.home_id}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            tado_zone_data = self.coordinator.data["zone"][self.zone_id]
        except KeyError:
            return

        self._attr_is_on = self.entity_description.state_fn(tado_zone_data)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                tado_zone_data
            )
        super()._handle_coordinator_update()
