"""Number platform for SunSynk integration — SOC battery cap controls."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunSynkConfigEntry, SunSynkCoordinator
from .const import DOMAIN
from .data_fetcher import TokenManager, async_write_settings
from .helpers import get_inverter_settings, inverter_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# cap1-cap6: (api_key, translation_key, settings_key)
CAP_DEFS: list[tuple[str, str, str]] = [
    ("cap1", "cap_soc_floor_1", "cap1"),
    ("cap2", "cap_soc_floor_2", "cap2"),
    ("cap3", "cap_soc_floor_3", "cap3"),
    ("cap4", "cap_soc_floor_4", "cap4"),
    ("cap5", "cap_soc_floor_5", "cap5"),
    ("cap6", "cap_soc_floor_6", "cap6"),
]

# Additional numeric settings: (api_key, translation_key, settings_key, min, max)
EXTRA_NUMBER_DEFS: list[tuple[str, str, str, float, float]] = [
    ("batteryRestartCap", "battery_restart_cap", "battery_restart_cap", 0, 100),
    ("batteryShutdownCap", "battery_shutdown_cap", "battery_shutdown_cap", 0, 100),
    (
        "batteryMaxCurrentCharge",
        "battery_max_charge_current",
        "battery_max_current_charge",
        0,
        250,
    ),
]


class SunSynkCapNumber(CoordinatorEntity, NumberEntity):
    """Number entity for SOC cap settings (cap1-cap6)."""

    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        api_key: str,
        translation_key: str,
        settings_key: str,
        token_manager: TokenManager,
        region_idx: int,
    ) -> None:
        """Initialise the cap number entity."""
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._sn = sn
        self._api_key = api_key
        self._settings_key = settings_key
        self._token_manager = token_manager
        self._region_idx = region_idx
        self._attr_unique_id = f"{DOMAIN}_inverter_{sn}_{settings_key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        was_available = getattr(self, "_attr_available", True)
        has_settings = (
            get_inverter_settings(self.coordinator, self._plant_id, self._sn)
            is not None
        )
        self._attr_available = has_settings
        if was_available and not has_settings:
            _LOGGER.warning("Entity %s is now unavailable", self._attr_unique_id)
        self._attr_native_value = self._compute_native_value() if has_settings else None
        super()._handle_coordinator_update()

    def _compute_native_value(self) -> float | None:
        """Return the current cap value from coordinator data."""
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        if not settings:
            return None
        val = getattr(settings, self._settings_key, None)
        if val is None:
            return None
        try:
            return float(val)
        except ValueError, TypeError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new cap value to the inverter."""
        int_val = str(int(value))
        _LOGGER.debug("Setting %s=%s for inverter %s", self._api_key, int_val, self._sn)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            {self._api_key: int_val},
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()


class SunSynkExtraNumber(CoordinatorEntity, NumberEntity):
    """Number entity for additional numeric inverter settings."""

    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        api_key: str,
        translation_key: str,
        settings_key: str,
        min_val: float,
        max_val: float,
        token_manager: TokenManager,
        region_idx: int,
    ) -> None:
        """Initialise the extra number entity."""
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._sn = sn
        self._api_key = api_key
        self._settings_key = settings_key
        self._token_manager = token_manager
        self._region_idx = region_idx
        self._attr_unique_id = f"{DOMAIN}_inverter_{sn}_{settings_key}"
        self._attr_translation_key = translation_key
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        was_available = getattr(self, "_attr_available", True)
        has_settings = (
            get_inverter_settings(self.coordinator, self._plant_id, self._sn)
            is not None
        )
        self._attr_available = has_settings
        if was_available and not has_settings:
            _LOGGER.warning("Entity %s is now unavailable", self._attr_unique_id)
        self._attr_native_value = self._compute_native_value() if has_settings else None
        super()._handle_coordinator_update()

    def _compute_native_value(self) -> float | None:
        """Return the current value from coordinator data."""
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        if not settings:
            return None
        val = getattr(settings, self._settings_key, None)
        if val is None:
            return None
        try:
            return float(val)
        except ValueError, TypeError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the inverter."""
        str_val = str(int(value))
        _LOGGER.debug("Setting %s=%s for inverter %s", self._api_key, str_val, self._sn)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            {self._api_key: str_val},
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SunSynk number platform."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    token_manager = runtime.token_manager
    region_idx: int = entry.data["region"]

    if not coordinator.data:
        return

    entities: list[NumberEntity] = []

    for plant_id, plant_data in coordinator.data.get("plants", {}).items():
        for sn, inv_data in plant_data.get("inverters", {}).items():
            if not inv_data.get("settings"):
                continue

            # Cap 1-6 number entities
            for api_key, name, settings_key in CAP_DEFS:
                entities.append(
                    SunSynkCapNumber(
                        coordinator,
                        plant_id,
                        sn,
                        api_key,
                        name,
                        settings_key,
                        token_manager,
                        region_idx,
                    )
                )

            # Extra numeric settings
            for api_key, name, settings_key, min_val, max_val in EXTRA_NUMBER_DEFS:
                entities.append(
                    SunSynkExtraNumber(
                        coordinator,
                        plant_id,
                        sn,
                        api_key,
                        name,
                        settings_key,
                        min_val,
                        max_val,
                        token_manager,
                        region_idx,
                    )
                )

    async_add_entities(entities)
