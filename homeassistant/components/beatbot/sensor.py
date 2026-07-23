"""Sensors for the Beatbot integration."""

from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity
from .iot.category import (
    BATTERY_CATEGORIES,
    CATEGORY_MAP,
    ERROR_BITS_BY_CATEGORY,
    STATUS_DISPLAY_MAP_BY_CATEGORY,
)


def _remove_obsolete_firmware_entity(
    hass: HomeAssistant, entry: BeatbotConfigEntry
) -> None:
    """Drop the registry entry for the removed BeatbotFirmwareSensor.

    Firmware now lives on the device registry (device_info.sw_version), so the
    old sensor.{device_id}_firmware entity is no longer created; evict any
    stale registry entry so users don't see a permanently-unavailable sensor.
    Matches by suffix so devices no longer in discovery are covered too.
    """
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain == "sensor" and (reg_entry.unique_id or "").endswith(
            "_firmware"
        ):
            registry.async_remove(reg_entry.entity_id)


def _remove_unsupported_battery_entities(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    device_ids: set[str],
) -> None:
    """Remove battery entities previously registered for mains-powered devices."""
    if not device_ids:
        return
    obsolete_unique_ids = {f"{device_id}_battery" for device_id in device_ids}
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain == "sensor" and reg_entry.unique_id in obsolete_unique_ids:
            registry.async_remove(reg_entry.entity_id)


class BeatbotStatusSensor(BeatbotEntity, SensorEntity):
    """Represent the device work status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "work_status"

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_status"
        category = CATEGORY_MAP.get(
            self.coordinator.data[self._device_id].product_category
        )
        assert category is not None

        self._status_map = STATUS_DISPLAY_MAP_BY_CATEGORY.get(category, {})

        self._attr_options = list(dict.fromkeys(self._status_map.values()))

    @property
    @override
    def native_value(self) -> str | None:
        """Return the translated work-status key."""
        return self._status_map.get(self.data.work_status)


class BeatbotBatterySensor(BeatbotEntity, SensorEntity):
    """Represent the device battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "battery"

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_battery"

    @property
    @override
    def native_value(self) -> int:
        """Return the battery percentage."""
        return self.data.battery_level


class BeatbotErrorSensor(BeatbotEntity, SensorEntity):
    """Decoded device error as a single readable value.

    The backend reports a bitmask via `sensor.error` (stored as
    `error_code`). This ENUM sensor decodes it to the *primary* active
    fault (lowest set bit) so a user sees "电量不足" rather than `4`. The
    full per-bit on/off breakdown is exposed as `extra_state_attributes`
    (so concurrent multi-bit faults are still inspectable). The vacuum's
    ERROR activity serves as the "any fault" binary hook.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "error"

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
        bits: list[tuple[str, int]],
    ) -> None:
        """Initialize the error sensor."""
        super().__init__(coordinator, device_id)
        self._bits = bits
        self._attr_unique_id = f"{device_id}_error"
        # ENUM options must contain every value native_value can return.
        self._attr_options = [key for key, _ in bits] + ["none"]

    @property
    @override
    def native_value(self) -> str:
        """Return the primary active error key."""
        for key, bit in self._bits:
            if self.data.error_code & bit:
                return key
        return "none"

    @property
    @override
    def extra_state_attributes(self) -> dict[str, bool]:
        """Per-bit on/off map. Keys are raw capability slugs (not translated)."""
        code = self.data.error_code
        return {key: bool(code & bit) for key, bit in self._bits}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot sensors."""
    coordinator = entry.runtime_data.coordinator
    _remove_obsolete_firmware_entity(hass, entry)
    unsupported_battery_device_ids = {
        device_id
        for device_id, device in coordinator.data.items()
        if CATEGORY_MAP.get(device.product_category) not in BATTERY_CATEGORIES
    }
    _remove_unsupported_battery_entities(hass, entry, unsupported_battery_device_ids)
    entities: list[SensorEntity] = []
    for device_id in coordinator.data:
        category = CATEGORY_MAP.get(coordinator.data[device_id].product_category)
        assert category is not None
        entities.append(BeatbotStatusSensor(coordinator, device_id))
        if category in BATTERY_CATEGORIES:
            entities.append(BeatbotBatterySensor(coordinator, device_id))
        # Only expose the decoded error sensor when the device's category
        # actually has a bit map to decode against.
        if bits := ERROR_BITS_BY_CATEGORY.get(category, []):
            entities.append(BeatbotErrorSensor(coordinator, device_id, bits))
    async_add_entities(entities)
