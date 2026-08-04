"""Event-count sensor platform for Agent DVR."""

from typing import override

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AgentDVRConfigEntry
from .const import DEVICE_TYPE_CAMERA, DOMAIN
from .coordinator import AgentDVREventCountCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up per-camera 24h event-count sensors."""
    data = entry.runtime_data
    main_coordinator = data.coordinator

    camera_keys = [
        oid_ot
        for oid_ot, device in main_coordinator.data["devices"].items()
        if device["typeID"] == DEVICE_TYPE_CAMERA
    ]
    if not camera_keys:
        return

    event_coordinator = AgentDVREventCountCoordinator(
        hass, entry, data.client, camera_keys
    )
    await event_coordinator.async_config_entry_first_refresh()

    async_add_entities(
        AgentDVREventCountSensor(event_coordinator, oid_ot, data.unique_id)
        for oid_ot in camera_keys
    )


class AgentDVREventCountSensor(
    CoordinatorEntity[AgentDVREventCountCoordinator], SensorEntity
):
    """Number of Agent DVR events for this camera in the last 24 hours."""

    _attr_has_entity_name = True
    _attr_translation_key = "events_24h"
    _attr_icon = "mdi:motion-sensor"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "events"

    def __init__(
        self,
        coordinator: AgentDVREventCountCoordinator,
        oid_ot: str,
        server_unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._oid_ot = oid_ot
        oid_str, ot_str = oid_ot.split("_")
        camera_unique_id = f"{server_unique_id}_{ot_str}_{oid_str}"
        self._attr_unique_id = f"{camera_unique_id}_events_24h"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, camera_unique_id)})

    @property
    @override
    def native_value(self) -> int | None:
        """Return the current event count."""
        return self.coordinator.data.get(self._oid_ot)
