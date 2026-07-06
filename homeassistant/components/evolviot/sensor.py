"""Sensor platform for EvolvIOT."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "sensor"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: EvolvIOTDataUpdateCoordinator = data[DATA_COORDINATOR]
    known = data[DATA_KNOWN_ENTITIES].setdefault(PLATFORM_DOMAIN, set())

    def add_new_entities() -> None:
        entities = []
        for entity in coordinator.entities_for_domain(PLATFORM_DOMAIN):
            entity_id = entity["entity_id"]
            if entity_id in known:
                continue
            known.add(entity_id)
            entities.append(EvolvIOTSensor(coordinator, entity))

        for device in _devices_with_entities(coordinator):
            device_id = str(device.get("id") or "")
            connection_entity_id = f"connection_mode::{device_id}"
            if not device_id or connection_entity_id in known:
                continue
            known.add(connection_entity_id)
            entities.append(EvolvIOTConnectionModeSensor(coordinator, device))

        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTSensor(EvolvIOTEntity, SensorEntity):
    """EvolvIOT sensor entity."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        value = self.backend_state.get("state")
        if value is None:
            return None
        try:
            number = float(value)
        except TypeError, ValueError:
            return str(value)
        return int(number) if number.is_integer() else number


class EvolvIOTConnectionModeSensor(
    CoordinatorEntity[EvolvIOTDataUpdateCoordinator],
    SensorEntity,
):
    """Connection mode diagnostic sensor for one EvolvIOT device."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_mode"

    def __init__(
        self,
        coordinator: EvolvIOTDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the connection mode sensor."""
        super().__init__(coordinator)
        self._device_id = str(device["id"])
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_connection_mode"
        self._attr_name = "Connection Mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=str(device.get("name") or "EvolvIOT Device"),
            manufacturer=str(device.get("manufacturer") or "EvolvIOT"),
            model=str(device.get("model") or "") or None,
        )

    @property
    def native_value(self) -> str:
        """Return active connection mode for this physical device."""
        local_available = False
        cloud_available = False

        for entity in _entities_for_device(self.coordinator, self._device_id):
            state = self.coordinator.states.get(str(entity.get("entity_id") or ""), {})
            if not state:
                continue
            local_available = local_available or bool(state.get("local_available"))
            cloud_available = cloud_available or bool(
                state.get("cloud_available", state.get("available", True))
            )

        if local_available:
            return "local"
        if cloud_available:
            return "cloud"
        return "offline"

    @property
    def available(self) -> bool:
        """Connection mode sensor is available while the device exists."""
        return any(_entities_for_device(self.coordinator, self._device_id))


def _devices_with_entities(
    coordinator: EvolvIOTDataUpdateCoordinator,
) -> list[dict[str, Any]]:
    """Return unique device payloads that have entities."""
    devices: dict[str, dict[str, Any]] = {}
    for entity in coordinator.entities.values():
        device = entity.get("device") or {}
        device_id = str(device.get("id") or "")
        if device_id:
            devices.setdefault(device_id, device)
    return list(devices.values())


def _entities_for_device(
    coordinator: EvolvIOTDataUpdateCoordinator,
    device_id: str,
) -> list[dict[str, Any]]:
    """Return entities for one physical device."""
    return [
        entity
        for entity in coordinator.entities.values()
        if str((entity.get("device") or {}).get("id") or "") == device_id
    ]
