"""Binary sensor platform for the Tewke integration.

Exposes boolean BME680 calibration status fields, delivered via CoAP
observation (local_push). Both are disabled by default as diagnostic values.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import TewkeEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytewke.data import ConfigData, SensorData

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry


@dataclass(frozen=True, kw_only=True)
class TewkeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tewke binary sensor entity."""

    value_fn: Callable[[SensorData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[TewkeBinarySensorEntityDescription, ...] = (
    TewkeBinarySensorEntityDescription(
        key="stabilisation_status",
        name="Stabilisation Status",
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.stabilisation_status,
    ),
    TewkeBinarySensorEntityDescription(
        key="run_in_status",
        name="Run-in Status",
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.run_in_status,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tewke binary sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    entities: list[TewkeBinarySensor | TewkeScreenBinarySensor] = []

    if coordinator.data.get("sensors") is not None:
        entities.extend(
            TewkeBinarySensor(coordinator=coordinator, description=description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        )

    if coordinator.data.get("config") is not None:
        entities.append(TewkeScreenBinarySensor(coordinator=coordinator))

    async_add_entities(entities)


class TewkeBinarySensor(TewkeEntity, BinarySensorEntity):
    """A Tewke BME680 calibration status binary sensor."""

    entity_description: TewkeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        description: TewkeBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        hardware_id = coordinator.data["config"].hardware_id
        self._attr_unique_id = f"{hardware_id}_sensor_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the sensor state."""
        sensors: SensorData | None = self.coordinator.data.get("sensors")
        if sensors is None:
            return None
        return self.entity_description.value_fn(sensors)


class TewkeScreenBinarySensor(TewkeEntity, BinarySensorEntity):
    """Binary sensor representing whether the Tewke panel screen is on."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Screen"

    def __init__(self, coordinator: TewkeCoordinator) -> None:
        """Initialise the screen sensor."""
        super().__init__(coordinator)
        hardware_id = coordinator.data["config"].hardware_id
        self._attr_unique_id = f"{hardware_id}_screen_on"

    @property
    def is_on(self) -> bool | None:
        """Return True when the panel screen is on."""
        config: ConfigData | None = self.coordinator.data.get("config")
        if config is None:
            return None
        return config.screen_on
