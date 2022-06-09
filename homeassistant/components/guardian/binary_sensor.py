"""Binary sensors for the Elexa Guardian integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PairedSensorEntity, ValveControllerEntity
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DATA_COORDINATOR,
    DATA_COORDINATOR_PAIRED_SENSOR,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_MOVED = "moved"

SENSOR_DESCRIPTION_AP_ENABLED = BinarySensorEntityDescription(
    key=SENSOR_KIND_AP_INFO,
    name="Onboard AP Enabled",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)
SENSOR_DESCRIPTION_LEAK_DETECTED = BinarySensorEntityDescription(
    key=SENSOR_KIND_LEAK_DETECTED,
    name="Leak Detected",
    device_class=BinarySensorDeviceClass.MOISTURE,
)
SENSOR_DESCRIPTION_MOVED = BinarySensorEntityDescription(
    key=SENSOR_KIND_MOVED,
    name="Recently Moved",
    device_class=BinarySensorDeviceClass.MOVING,
    entity_category=EntityCategory.DIAGNOSTIC,
)

PAIRED_SENSOR_DESCRIPTIONS = (
    SENSOR_DESCRIPTION_LEAK_DETECTED,
    SENSOR_DESCRIPTION_MOVED,
)
VALVE_CONTROLLER_DESCRIPTIONS = (
    SENSOR_DESCRIPTION_AP_ENABLED,
    SENSOR_DESCRIPTION_LEAK_DETECTED,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""

    @callback
    def add_new_paired_sensor(uid: str) -> None:
        """Add a new paired sensor."""
        coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR_PAIRED_SENSOR][
            uid
        ]

        async_add_entities(
            [
                PairedSensorBinarySensor(entry, coordinator, description)
                for description in PAIRED_SENSOR_DESCRIPTIONS
            ]
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
            entry, hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR], description
        )
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    ]

    # Add all paired sensor-specific binary sensors:
    sensors.extend(
        [
            PairedSensorBinarySensor(entry, coordinator, description)
            for coordinator in hass.data[DOMAIN][entry.entry_id][
                DATA_COORDINATOR_PAIRED_SENSOR
            ].values()
            for description in PAIRED_SENSOR_DESCRIPTIONS
        ]
    )

    async_add_entities(sensors)


class PairedSensorBinarySensor(PairedSensorEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, description)

        self._attr_is_on = True

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self.entity_description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_is_on = self.coordinator.data["wet"]
        elif self.entity_description.key == SENSOR_KIND_MOVED:
            self._attr_is_on = self.coordinator.data["moved"]


class ValveControllerBinarySensor(ValveControllerEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, DataUpdateCoordinator],
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, description)

        self._attr_is_on = True

    async def _async_continue_entity_setup(self) -> None:
        """Add an API listener."""
        if self.entity_description.key == SENSOR_KIND_AP_INFO:
            self.async_add_coordinator_update_listener(API_WIFI_STATUS)
        elif self.entity_description.key == SENSOR_KIND_LEAK_DETECTED:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self.entity_description.key == SENSOR_KIND_AP_INFO:
            self._attr_available = self.coordinators[
                API_WIFI_STATUS
            ].last_update_success
            self._attr_is_on = self.coordinators[API_WIFI_STATUS].data[
                "station_connected"
            ]
            self._attr_extra_state_attributes.update(
                {
                    ATTR_CONNECTED_CLIENTS: self.coordinators[API_WIFI_STATUS].data.get(
                        "ap_clients"
                    )
                }
            )
        elif self.entity_description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_available = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
            self._attr_is_on = self.coordinators[API_SYSTEM_ONBOARD_SENSOR_STATUS].data[
                "wet"
            ]
