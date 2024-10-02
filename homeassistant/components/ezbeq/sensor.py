"""Sensor platform for the ezbeq Profile Loader integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EzBEQConfigEntry
from .const import CURRENT_PROFILE, STATE_UNLOADED
from .coordinator import EzBEQCoordinator
from .entity import EzBEQEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EzBEQSensorEntityDescription(SensorEntityDescription):
    """Describe EzBEQ sensor entity."""

    value_fn: Callable[[EzBEQCoordinator, str], StateType]


SENSORS: tuple[EzBEQSensorEntityDescription, ...] = (
    EzBEQSensorEntityDescription(
        key=CURRENT_PROFILE,
        value_fn=(
            lambda coordinator, device_name: coordinator.client.get_device_profile(
                device_name
            )
            if coordinator.client.get_device_profile(device_name) != ""
            else STATE_UNLOADED
        ),
        translation_key=CURRENT_PROFILE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzBEQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = entry.runtime_data
    _LOGGER.debug("Found %s devices", len(coordinator.client.device_info))
    async_add_entities(
        EzBEQSensor(coordinator, description, device.name)
        for device in coordinator.client.device_info
        for description in SENSORS
    )


class EzBEQSensor(EzBEQEntity, SensorEntity):
    """Base class for EzBEQ sensors."""

    entity_description: EzBEQSensorEntityDescription

    def __init__(
        self,
        coordinator: EzBEQCoordinator,
        description: EzBEQSensorEntityDescription,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{device_name}_{description.key}"
        )
        self._device_name = device_name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator, self._device_name)
