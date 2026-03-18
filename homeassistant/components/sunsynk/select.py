"""Select platform for SunSynk integration — sell time and work mode controls."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunSynkConfigEntry, SunSynkCoordinator
from .const import DOMAIN, VALID_TIME_SLOTS
from .data_fetcher import TokenManager, async_write_settings
from .helpers import get_inverter_settings, inverter_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# sellTime1-sellTime6: (api_key, translation_key, settings_key)
SELL_TIME_DEFS: list[tuple[str, str, str]] = [
    ("sellTime1", "sell_time_1", "sell_time1"),
    ("sellTime2", "sell_time_2", "sell_time2"),
    ("sellTime3", "sell_time_3", "sell_time3"),
    ("sellTime4", "sell_time_4", "sell_time4"),
    ("sellTime5", "sell_time_5", "sell_time5"),
    ("sellTime6", "sell_time_6", "sell_time6"),
]

SYS_WORK_MODES = ["0", "1", "2", "3"]


class SunSynkSellTimeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for sell time slot settings."""

    _attr_options = VALID_TIME_SLOTS
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
        """Initialise the sell time select entity."""
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
        self._attr_current_option = (
            self._compute_current_option() if has_settings else None
        )
        super()._handle_coordinator_update()

    def _compute_current_option(self) -> str | None:
        """Return the current sell time value."""
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        if not settings:
            return None
        val: str | None = getattr(settings, self._settings_key, None)
        if val and val in VALID_TIME_SLOTS:
            return val
        return None

    async def async_select_option(self, option: str) -> None:
        """Write the selected time to the inverter."""
        if option not in VALID_TIME_SLOTS:
            _LOGGER.warning("Invalid time slot: %s", option)
            return
        _LOGGER.debug("Setting %s=%s for inverter %s", self._api_key, option, self._sn)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            {self._api_key: option},
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()


class SunSynkSysWorkModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for system work mode."""

    _attr_options = SYS_WORK_MODES
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        token_manager: TokenManager,
        region_idx: int,
    ) -> None:
        """Initialise the system work mode select entity."""
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._sn = sn
        self._token_manager = token_manager
        self._region_idx = region_idx
        self._attr_unique_id = f"{DOMAIN}_inverter_{sn}_sys_work_mode"
        self._attr_translation_key = "sys_work_mode"
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
        self._attr_current_option = (
            self._compute_current_option() if has_settings else None
        )
        super()._handle_coordinator_update()

    def _compute_current_option(self) -> str | None:
        """Return the current work mode."""
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        if not settings:
            return None
        val = getattr(settings, "sys_work_mode", None)
        if val is not None:
            return str(val)
        return None

    async def async_select_option(self, option: str) -> None:
        """Write the selected work mode to the inverter."""
        _LOGGER.debug("Setting sysWorkMode=%s for inverter %s", option, self._sn)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            {"sysWorkMode": option},
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SunSynk select platform."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    token_manager = runtime.token_manager
    region_idx: int = entry.data["region"]

    if not coordinator.data:
        return

    entities: list[SelectEntity] = []

    for plant_id, plant_data in coordinator.data.get("plants", {}).items():
        for sn, inv_data in plant_data.get("inverters", {}).items():
            if not inv_data.get("settings"):
                continue

            # Sell time 1-6 select entities
            for api_key, name, settings_key in SELL_TIME_DEFS:
                entities.append(
                    SunSynkSellTimeSelect(
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

            # System work mode
            entities.append(
                SunSynkSysWorkModeSelect(
                    coordinator,
                    plant_id,
                    sn,
                    token_manager,
                    region_idx,
                )
            )

    async_add_entities(entities)
