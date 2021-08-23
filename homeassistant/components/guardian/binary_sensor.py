"""Binary sensors for the Elexa Guardian integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOVING,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PairedSensorEntity, ValveControllerEntity
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DATA_COORDINATOR,
    DATA_COORDINATOR_PAIRED_SENSOR,
    DATA_UNSUB_DISPATCHER_CONNECT,
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
    device_class=DEVICE_CLASS_CONNECTIVITY,
)
SENSOR_DESCRIPTION_LEAK_DETECTED = BinarySensorEntityDescription(
    key=SENSOR_KIND_LEAK_DETECTED,
    name="Leak Detected",
    device_class=DEVICE_CLASS_MOISTURE,
)
SENSOR_DESCRIPTION_MOVED = BinarySensorEntityDescription(
    key=SENSOR_KIND_MOVED, name="Recently Moved", device_class=DEVICE_CLASS_MOVING
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
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][entry.entry_id][
            uid
        ]

        entities = []
        for description in PAIRED_SENSOR_DESCRIPTIONS:
            entities.append(PairedSensorBinarySensor(entry, coordinator, description))

        async_add_entities(entities)

    # Handle adding paired sensors after HASS startup:
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT][entry.entry_id].append(
        async_dispatcher_connect(
            hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(entry.data[CONF_UID]),
            add_new_paired_sensor,
        )
    )

    sensors: list[PairedSensorBinarySensor | ValveControllerBinarySensor] = []

    # Add all valve controller-specific binary sensors:
    for description in VALVE_CONTROLLER_DESCRIPTIONS:
        sensors.append(
            ValveControllerBinarySensor(
                entry, hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id], description
            )
        )

    # Add all paired sensor-specific binary sensors:
    for coordinator in hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][
        entry.entry_id
    ].values():
        for description in PAIRED_SENSOR_DESCRIPTIONS:
            sensors.append(PairedSensorBinarySensor(entry, coordinator, description))

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
        if self._description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_is_on = self.coordinator.data["wet"]
        elif self._description.key == SENSOR_KIND_MOVED:
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
        if self._description.key == SENSOR_KIND_AP_INFO:
            self.async_add_coordinator_update_listener(API_WIFI_STATUS)
        elif self._description.key == SENSOR_KIND_LEAK_DETECTED:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._description.key == SENSOR_KIND_AP_INFO:
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
        elif self._description.key == SENSOR_KIND_LEAK_DETECTED:
            self._attr_available = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
            self._attr_is_on = self.coordinators[API_SYSTEM_ONBOARD_SENSOR_STATUS].data[
                "wet"
            ]
