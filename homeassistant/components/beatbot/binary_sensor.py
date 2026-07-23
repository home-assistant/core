"""Binary sensors for the Beatbot integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity
from .iot.category import (
    CATEGORY_MAP,
    CHARGING_STATUS_CODES_BY_CATEGORY,
    ERROR_BITS_BY_CATEGORY,
)


class BeatbotOnlineSensor(BeatbotEntity, BinarySensorEntity):
    """Represent the device cloud connectivity state."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_online"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the device is online."""
        return self.data.is_online


class BeatbotChargingSensor(BeatbotEntity, BinarySensorEntity):
    """Battery charging indicator derived from `work_status`.

    `VacuumActivity` has no CHARGING state, and the vacuum entity no longer
    carries `battery_level` (it lives on the battery sensor), so charging is
    exposed as a dedicated `BATTERY_CHARGING` binary sensor: on when the
    device's `work_status` code is in its category's charging-code set
    (`CHARGING_STATUS_CODES_BY_CATEGORY`).
    """

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "charging"

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
        charging_codes: frozenset[int] | set[int],
    ) -> None:
        """Initialize the charging sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_charging"
        self._charging_codes = charging_codes

    @property
    @override
    def available(self) -> bool:
        """Return whether charging state is available."""
        return self.data.is_online and self.coordinator.last_update_success

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the device is charging."""
        return self.data.work_status in self._charging_codes


_OBSOLETE_BIT_KEYS: frozenset[str] = frozenset(
    key for bits in ERROR_BITS_BY_CATEGORY.values() for key, _ in bits
)
# Suffixes of the unique_ids of the old per-bit binary_sensor error entities
# (BeatbotErrorBitSensor, unique_id f"{device_id}_{key}"), now replaced by the
# sensor-domain error ENUM. Used to evict stale registry entries.
_OBSOLETE_ERROR_ENTITY_SUFFIXES: frozenset[str] = _OBSOLETE_BIT_KEYS | {"error_bit"}


def _remove_obsolete_error_entities(
    hass: HomeAssistant, entry: BeatbotConfigEntry
) -> None:
    """Drop registry entries for obsolete binary_sensor error-bit entities.

    Matches by suffix (unique_id was f"{device_id}_{key}") rather than against
    the current coordinator.data device list, so devices no longer in
    discovery — removed from the account, offline, or filtered out by the
    product allow-list — are still cleaned up, not just the ones present now.
    """
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain != "binary_sensor":
            continue
        uid = reg_entry.unique_id or ""
        if any(
            uid.endswith(f"_{suffix}") for suffix in _OBSOLETE_ERROR_ENTITY_SUFFIXES
        ):
            registry.async_remove(reg_entry.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot binary sensors."""
    coordinator = entry.runtime_data.coordinator
    _remove_obsolete_error_entities(hass, entry)
    entities: list[BinarySensorEntity] = []
    for device_id, device in coordinator.data.items():
        entities.append(BeatbotOnlineSensor(coordinator, device_id))
        category = CATEGORY_MAP.get(device.product_category)
        assert category is not None
        charging_codes = CHARGING_STATUS_CODES_BY_CATEGORY.get(category, set())
        if charging_codes:
            entities.append(
                BeatbotChargingSensor(coordinator, device_id, charging_codes)
            )
    async_add_entities(entities)
