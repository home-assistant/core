"""Binary sensors for the Elexa Guardian integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GuardianData
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    CONF_UID,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)
from .coordinator import GuardianDataUpdateCoordinator
from .entity import (
    PairedSensorEntity,
    ValveControllerEntity,
    ValveControllerEntityDescription,
)
from .util import (
    EntityDomainReplacementStrategy,
    async_finish_entity_domain_replacements,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_MOVED = "moved"


@dataclass(frozen=True, kw_only=True)
class PairedSensorBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Guardian paired sensor binary sensor."""

    is_on_fn: Callable[[dict[str, Any]], bool]


@dataclass(frozen=True, kw_only=True)
class ValveControllerBinarySensorDescription(
    BinarySensorEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller binary sensor."""

    is_on_fn: Callable[[dict[str, Any]], bool]


PAIRED_SENSOR_DESCRIPTIONS = (
    PairedSensorBinarySensorDescription(
        key=SENSOR_KIND_LEAK_DETECTED,
        translation_key="leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        is_on_fn=lambda data: data["wet"],
    ),
    PairedSensorBinarySensorDescription(
        key=SENSOR_KIND_MOVED,
        translation_key="moved",
        device_class=BinarySensorDeviceClass.MOVING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data["moved"],
    ),
)

VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerBinarySensorDescription(
        key=SENSOR_KIND_LEAK_DETECTED,
        translation_key="leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        api_category=API_SYSTEM_ONBOARD_SENSOR_STATUS,
        is_on_fn=lambda data: data["wet"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guardian switches based on a config entry."""
    data: GuardianData = hass.data[DOMAIN][entry.entry_id]
    uid = entry.data[CONF_UID]

    async_finish_entity_domain_replacements(
        hass,
        entry,
        (
            EntityDomainReplacementStrategy(
                BINARY_SENSOR_DOMAIN,
                f"{uid}_ap_enabled",
            ),
        ),
    )

    @callback
    def add_new_paired_sensor(uid: str) -> None:
        """Add a new paired sensor."""
        async_add_entities(
            PairedSensorBinarySensor(
                entry, data.paired_sensor_manager.coordinators[uid], description
            )
            for description in PAIRED_SENSOR_DESCRIPTIONS
        )

    # Handle adding paired sensors after HASS startup:
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(entry.data[CONF_UID]),
            add_new_paired_sensor,
        )
    )

    # Add all valve controller-specific binary sensors:
    sensors: list[PairedSensorBinarySensor | ValveControllerBinarySensor] = [
        ValveControllerBinarySensor(
            entry, data.valve_controller_coordinators, description
        )
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    ]

    # Add all paired sensor-specific binary sensors:
    sensors.extend(
        [
            PairedSensorBinarySensor(entry, coordinator, description)
            for coordinator in data.paired_sensor_manager.coordinators.values()
            for description in PAIRED_SENSOR_DESCRIPTIONS
        ]
    )

    async_add_entities(sensors)


class PairedSensorBinarySensor(PairedSensorEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    entity_description: PairedSensorBinarySensorDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: GuardianDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, description)

        self._attr_is_on = True

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)


class ValveControllerBinarySensor(ValveControllerEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    entity_description: ValveControllerBinarySensorDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, GuardianDataUpdateCoordinator],
        description: ValveControllerBinarySensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, description)

        self._attr_is_on = True

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
