"""Sensor platform for Sony Projector."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import (  # type: ignore[attr-defined]
    DeviceInfo,
    EntityCategory,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SonyProjectorConfigEntry
from .const import CONF_MODEL, CONF_SERIAL, CONF_TITLE, DEFAULT_NAME, DOMAIN
from .coordinator import SonyProjectorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up projector sensors."""

    coordinator = entry.runtime_data.coordinator
    identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        manufacturer="Sony",
        model=entry.data.get(CONF_MODEL),
        name=entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME),
    )

    sensors: list[SonyProjectorBaseSensor] = [
        SonyProjectorLampHoursSensor(entry, coordinator, device_info),
        SonyProjectorModelSensor(entry, coordinator, device_info),
    ]

    # Only add serial sensor when we actually know the serial.
    if entry.data.get(CONF_SERIAL) or (coordinator.data and coordinator.data.serial):
        sensors.append(SonyProjectorSerialSensor(entry, coordinator, device_info))

    async_add_entities(sensors)


class SonyProjectorBaseSensor(
    CoordinatorEntity[SonyProjectorCoordinator], SensorEntity
):
    """Base class for Sony projector sensors."""

    _attr_has_entity_name = True

    def __init__(self, entry, coordinator, device_info: DeviceInfo) -> None:
        """Initialize the base sensor."""

        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device_info
        self._identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]

    @property
    def available(self) -> bool:
        """Return whether data is available."""

        return self.coordinator.last_update_success


class SonyProjectorLampHoursSensor(SonyProjectorBaseSensor):
    """Sensor representing lamp usage hours."""

    _attr_translation_key = "lamp_hours"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry, coordinator, device_info) -> None:
        """Initialize lamp hour sensor."""

        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{self._identifier}-lamp_hours"

    @property
    def native_value(self) -> int | None:
        """Return the total lamp hours."""

        if (data := self.coordinator.data) is None:
            return None
        return data.lamp_hours


class SonyProjectorModelSensor(SonyProjectorBaseSensor):
    """Sensor for projector model information."""

    _attr_translation_key = "model"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, coordinator, device_info) -> None:
        """Initialize the model sensor."""

        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{self._identifier}-model"

    @property
    def native_value(self) -> str | None:
        """Return the model name."""

        if (data := self.coordinator.data) is not None and data.model:
            return data.model
        return self._entry.data.get(CONF_MODEL)


class SonyProjectorSerialSensor(SonyProjectorBaseSensor):
    """Sensor for projector serial number."""

    _attr_translation_key = "serial"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, coordinator, device_info) -> None:
        """Initialize the serial sensor."""

        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{self._identifier}-serial"

    @property
    def native_value(self) -> str | None:
        """Return the serial number."""

        if (data := self.coordinator.data) is not None and data.serial:
            return data.serial
        return self._entry.data.get(CONF_SERIAL)
