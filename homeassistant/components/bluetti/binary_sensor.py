"""Binary sensor platform for the BLUETTI integration."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BluettiConfigEntry
from .entity import BluettiEntity
from .models import BluettiData, BluettiDevice, BluettiState

# Entities only read from the coordinator and never poll or call the API
# themselves, so there is no need to limit concurrent updates.
PARALLEL_UPDATES = 0

BINARY_SENSOR_MAP: dict[str, dict[str, Any]] = {
    "onLine": {
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "name": "Online",
    }
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Bluetti binary sensors from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices
    entities: list[BluettiBinarySensor] = []

    for device in bluetti_devices.devices:
        entities.extend(
            BluettiBinarySensor(device, state, BINARY_SENSOR_MAP[state.fn_code])
            for state in device.states
            if state.fn_type == "SENSOR" and state.fn_code in BINARY_SENSOR_MAP
        )

    if entities:
        async_add_entities(entities)

    return True


class BluettiBinarySensor(BluettiEntity, BinarySensorEntity):
    """Bluetti binary sensor for online/offline state."""

    def __init__(self, device: BluettiDevice, state: BluettiState, meta: dict[str, Any]) -> None:
        """Initialize the binary sensor from its cloud state and static metadata."""
        super().__init__(device, state)
        self._meta = meta

        self._attr_name = meta["name"]
        self._attr_device_class = meta.get("device_class")
        # Connectivity status is diagnostic information, not a primary
        # measurement.
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if the device reports itself online."""
        return self._state_obj.fn_value == "1"
