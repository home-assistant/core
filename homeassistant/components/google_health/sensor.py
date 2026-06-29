"""Sensor platform for the Google Health integration."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleHealthConfigEntry, GoogleHealthCoordinator
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class GoogleHealthSensorEntityDescription(SensorEntityDescription):
    """Class describing Google Health sensor entities."""

    api_namespace: str


STEPS_SENSOR_DESCRIPTION = GoogleHealthSensorEntityDescription(
    key="steps",
    translation_key="steps",
    native_unit_of_measurement="steps",
    icon="mdi:walk",
    state_class=SensorStateClass.TOTAL_INCREASING,
    api_namespace="steps",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleHealthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Health sensor platform."""
    coordinator = entry.runtime_data
    scopes = entry.data.get("token", {}).get("scope", "").split()

    entities = []
    for description in (STEPS_SENSOR_DESCRIPTION,):
        sub_api = getattr(coordinator.api, description.api_namespace)
        required_scopes = sub_api.required_read_scopes
        if all(scope in scopes for scope in required_scopes):
            entities.append(
                GoogleHealthStepsSensor(coordinator, entry.entry_id, description)
            )

    if entities:
        async_add_entities(entities)


class GoogleHealthStepsSensor(CoordinatorEntity[GoogleHealthCoordinator], SensorEntity):
    """Steps sensor entity."""

    _attr_has_entity_name = True
    entity_description: GoogleHealthSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleHealthCoordinator,
        entry_id: str,
        description: GoogleHealthSensorEntityDescription,
    ) -> None:
        """Initialize the steps sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Google Health",
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the steps count."""
        return self.coordinator.data.get(self.entity_description.key, 0)
