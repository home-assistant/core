"""Support for sensors."""

from typing import TYPE_CHECKING, Final, cast

from aiocomelit.api import ComelitSerialBridgeObject, ComelitVedoZoneObject
from aiocomelit.const import ALARM_ZONE, OTHER, AlarmZoneState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import Platform, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ObjectClassType
from .coordinator import ComelitConfigEntry, ComelitSerialBridge, ComelitVedoSystem
from .entity import ComelitBridgeBaseEntity
from .utils import new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SENSOR_BRIDGE_TYPES: Final = (
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)

SENSOR_VEDO_TYPES: Final = (
    SensorEntityDescription(
        key="human_status",
        translation_key="zone_status",
        name=None,
        device_class=SensorDeviceClass.ENUM,
        options=[zone_state.value for zone_state in AlarmZoneState],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit sensors."""

    coordinator = config_entry.runtime_data
    is_bridge = isinstance(coordinator, ComelitSerialBridge)

    if TYPE_CHECKING:
        if is_bridge:
            assert isinstance(coordinator, ComelitSerialBridge)
        else:
            assert isinstance(coordinator, ComelitVedoSystem)

    def _add_new_bridge_entities(
        new_devices: list[ObjectClassType], dev_type: str
    ) -> None:
        """Add entities for new monitors."""
        assert isinstance(coordinator, ComelitSerialBridge)
        entities = [
            ComelitBridgeSensorEntity(
                coordinator, device, config_entry.entry_id, sensor_desc
            )
            for sensor_desc in SENSOR_BRIDGE_TYPES
            for device in coordinator.data[dev_type].values()
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    def _add_new_vedo_entities(
        new_devices: list[ObjectClassType], dev_type: str
    ) -> None:
        """Add entities for new monitors."""
        entities = [
            ComelitVedoSensorEntity(
                coordinator, device, config_entry.entry_id, sensor_desc
            )
            for sensor_desc in SENSOR_VEDO_TYPES
            for device in coordinator.data[dev_type].values()
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    # Bridge native sensors
    if is_bridge:
        config_entry.async_on_unload(
            new_device_listener(coordinator, _add_new_bridge_entities, OTHER)
        )

    # Alarm sensors (both via Bridge or VedoSystem)
    if coordinator.vedo_pin:
        await _async_migrate_zone_sensor_unique_ids(hass, config_entry)
        config_entry.async_on_unload(
            new_device_listener(coordinator, _add_new_vedo_entities, ALARM_ZONE)
        )


async def _async_migrate_zone_sensor_unique_ids(
    hass: HomeAssistant, config_entry: ComelitConfigEntry
) -> None:
    """Migrate legacy VEDO zone sensor unique IDs to include sensor key."""
    device_registry = dr.async_get(hass)

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        if entry.domain != Platform.SENSOR or entry.device_id is None:
            return None

        if not (
            zone_index := entry.unique_id.removeprefix(f"{config_entry.entry_id}-")
        ).isdigit():
            return None

        if not (device_entry := device_registry.async_get(entry.device_id)):
            return None

        if not any(
            platform == DOMAIN
            and identifier.startswith(f"{config_entry.entry_id}-zone-")
            for platform, identifier in device_entry.identifiers
        ):
            return None

        return {"new_unique_id": f"{config_entry.entry_id}-human_status-{zone_index}"}

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)


class ComelitBridgeSensorEntity(ComelitBridgeBaseEntity, SensorEntity):
    """Sensor device."""

    _attr_name = None

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        super().__init__(coordinator, device, config_entry_entry_id)

        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return cast(
            StateType,
            getattr(
                self.coordinator.data[OTHER][self._device.index],
                self.entity_description.key,
            ),
        )


class ComelitVedoSensorEntity(
    CoordinatorEntity[ComelitVedoSystem | ComelitSerialBridge], SensorEntity
):
    """Sensor device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ComelitVedoSystem | ComelitSerialBridge,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._zone_index = zone.index
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{description.key}-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone, "zone")

        self.entity_description = description

    @property
    def _zone_object(self) -> ComelitVedoZoneObject:
        """Zone object."""
        return cast(
            ComelitVedoZoneObject, self.coordinator.data[ALARM_ZONE][self._zone_index]
        )

    @property
    def available(self) -> bool:
        """Sensor availability."""
        return self._zone_object.human_status != AlarmZoneState.UNAVAILABLE

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        if (status := self._zone_object.human_status) == AlarmZoneState.UNKNOWN:
            return None

        return cast(str, status.value)
