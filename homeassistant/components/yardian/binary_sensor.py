"""Binary sensors for Yardian integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yardian binary sensors."""
    coordinator: YardianUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = [
        YardianWateringRunningBinarySensor(coordinator),
        YardianStandbyBinarySensor(coordinator),
        YardianFreezePreventBinarySensor(coordinator),
    ]

    # Per-zone enabled sensors (diagnostic, disabled by default)
    entities.extend(
        YardianZoneEnabledBinarySensor(coordinator, zone_id)
        for zone_id in range(len(coordinator.data.zones))
    )

    async_add_entities(entities)


class _BaseYardianBinarySensor(
    CoordinatorEntity[YardianUpdateCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info


class YardianWateringRunningBinarySensor(_BaseYardianBinarySensor):
    """Indicates if any zone is currently irrigating."""

    _attr_translation_key = "watering_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize watering running sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.yid}-watering-running"

    @property
    def is_on(self) -> bool | None:
        """Return True if any zone is active."""
        return bool(self.coordinator.data.active_zones)


class YardianStandbyBinarySensor(_BaseYardianBinarySensor):
    """Indicates if controller is in standby mode."""

    _attr_translation_key = "standby"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize standby diagnostic sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.yid}-standby"

    @property
    def is_on(self) -> bool | None:
        """Return True if controller is in standby."""
        return bool(self.coordinator.data.oper_info.get("iStandby", 0))


class YardianFreezePreventBinarySensor(_BaseYardianBinarySensor):
    """Indicates if freeze prevent is active."""

    _attr_translation_key = "freeze_prevent"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize freeze prevent diagnostic sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.yid}-freeze-prevent"

    @property
    def is_on(self) -> bool | None:
        """Return True if freeze prevent is active."""
        return bool(self.coordinator.data.oper_info.get("fFreezePrevent", 0))


class YardianZoneEnabledBinarySensor(_BaseYardianBinarySensor):
    """Per-zone enabled flag."""

    _attr_translation_key = "zone_enabled"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: YardianUpdateCoordinator, zone_id: int) -> None:
        """Initialize per-zone enabled diagnostic sensor."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.yid}-zone-enabled-{zone_id}"
        self._attr_translation_placeholders = {"zone": str(zone_id + 1)}

    @property
    def is_on(self) -> bool | None:
        """Return True if the zone is enabled on controller."""
        try:
            return self.coordinator.data.zones[self._zone_id][1] == 1
        except (IndexError, TypeError):
            return None
