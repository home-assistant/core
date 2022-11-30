"""Binary sensors for the Elexa Guardian integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    GuardianData,
    PairedSensorEntity,
    ValveControllerEntity,
    ValveControllerEntityDescription,
)
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    CONF_UID,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)
from .util import (
    EntityDomainReplacementStrategy,
    GuardianDataUpdateCoordinator,
    async_finish_entity_domain_replacements,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_MOVED = "moved"


@dataclass
class ValveControllerBinarySensorDescription(
    BinarySensorEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller binary sensor."""


PAIRED_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key=SENSOR_KIND_LEAK_DETECTED,
        name="Leak detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key=SENSOR_KIND_MOVED,
        name="Recently moved",
        device_class=BinarySensorDeviceClass.MOVING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerBinarySensorDescription(
        key=SENSOR_KIND_LEAK_DETECTED,
        name="Leak detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
        api_category=API_SYSTEM_ONBOARD_SENSOR_STATUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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
                f"switch.guardian_valve_controller_{uid}_onboard_ap",
                "2022.12.0",
                remove_old_entity=True,
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

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: GuardianDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, description)

        self._attr_is_on = True

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity's underlying data."""
        if self.entity_description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_is_on = self.coordinator.data["wet"]
        elif self.entity_description.key == SENSOR_KIND_MOVED:
            self._attr_is_on = self.coordinator.data["moved"]


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

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self.entity_description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_is_on = self.coordinator.data["wet"]
