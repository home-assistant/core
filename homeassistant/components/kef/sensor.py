"""Sensor platform for KEF speakers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KefConfigEntry, KefCoordinator, KefData


@dataclass(frozen=True, kw_only=True)
class KefSensorEntityDescription(SensorEntityDescription):
    """Description of a KEF sensor entity."""

    value_fn: Callable[[KefData], str | int | None]


SENSORS: tuple[KefSensorEntityDescription, ...] = (
    KefSensorEntityDescription(
        key="audio_codec",
        translation_key="audio_codec",
        name="Audio codec",
        icon="mdi:surround-sound",
        value_fn=lambda data: data.audio_codec,
    ),
    KefSensorEntityDescription(
        key="sample_rate",
        translation_key="sample_rate",
        name="Sample rate",
        icon="mdi:sine-wave",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sample_rate,
    ),
    KefSensorEntityDescription(
        key="audio_channels",
        translation_key="audio_channels",
        name="Audio channels",
        icon="mdi:surround-sound",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.audio_channels,
    ),
    KefSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        name="WiFi signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_signal,
    ),
    KefSensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        name="WiFi SSID",
        icon="mdi:wifi",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_ssid,
    ),
    KefSensorEntityDescription(
        key="wifi_frequency",
        translation_key="wifi_frequency",
        name="WiFi frequency",
        icon="mdi:wifi",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_frequency,
    ),
    KefSensorEntityDescription(
        key="media_service",
        translation_key="media_service",
        name="Media service",
        icon="mdi:music-box",
        value_fn=lambda data: data.media_service,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up KEF sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        KefSensorEntity(coordinator, entry, description)
        for description in SENSORS
    )


class KefSensorEntity(CoordinatorEntity[KefCoordinator], SensorEntity):
    """Sensor entity for KEF speakers."""

    entity_description: KefSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: KefConfigEntry,
        description: KefSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        assert entry.unique_id is not None
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
        )

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
