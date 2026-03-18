"""Switch platform for SunSynk integration — timer and mode toggles."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
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

# Paired timer toggles: (api_key, translation_key, settings_key, paired_api_key, paired_settings_key)
TIMER_TOGGLE_DEFS: list[tuple[str, str, str, str, str]] = [
    ("time1on", "timer_1_on", "time1on", "genTime1on", "gen_time1on"),
    ("time2on", "timer_2_on", "time2on", "genTime2on", "gen_time2on"),
    ("time3on", "timer_3_on", "time3on", "genTime3on", "gen_time3on"),
    ("time4on", "timer_4_on", "time4on", "genTime4on", "gen_time4on"),
    ("time5on", "timer_5_on", "time5on", "genTime5on", "gen_time5on"),
    ("time6on", "timer_6_on", "time6on", "genTime6on", "gen_time6on"),
]

GEN_TIMER_TOGGLE_DEFS: list[tuple[str, str, str, str, str]] = [
    ("genTime1on", "gen_timer_1_on", "gen_time1on", "time1on", "time1on"),
    ("genTime2on", "gen_timer_2_on", "gen_time2on", "time2on", "time2on"),
    ("genTime3on", "gen_timer_3_on", "gen_time3on", "time3on", "time3on"),
    ("genTime4on", "gen_timer_4_on", "gen_time4on", "time4on", "time4on"),
    ("genTime5on", "gen_timer_5_on", "gen_time5on", "time5on", "time5on"),
    ("genTime6on", "gen_timer_6_on", "gen_time6on", "time6on", "time6on"),
]

# Simple boolean toggles: (api_key, translation_key, settings_key)
SIMPLE_TOGGLE_DEFS: list[tuple[str, str, str]] = [
    ("peakAndVallery", "use_timer", "peak_and_vallery"),
    ("energyMode", "energy_mode", "energy_mode"),
]


def _bool_to_api(value: bool) -> str:
    """Convert bool to API string value."""
    return "1" if value else "0"


def _api_to_bool(value: Any) -> bool:
    """Convert API string value to bool."""
    if value is None:
        return False
    return str(value) in ("1", "true", "True", "on")


class SunSynkPairedTimerSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for timer toggles that must be sent with their paired value."""

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
        paired_api_key: str,
        paired_settings_key: str,
        token_manager: TokenManager,
        region_idx: int,
    ) -> None:
        """Initialise the paired timer switch entity."""
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._sn = sn
        self._api_key = api_key
        self._settings_key = settings_key
        self._paired_api_key = paired_api_key
        self._paired_settings_key = paired_settings_key
        self._token_manager = token_manager
        self._region_idx = region_idx
        self._attr_unique_id = f"{DOMAIN}_inverter_{sn}_{settings_key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        was_available = getattr(self, "_attr_available", True)
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        self._attr_available = settings is not None
        if was_available and settings is None:
            _LOGGER.warning("Entity %s is now unavailable", self._attr_unique_id)
        if settings:
            val = getattr(settings, self._settings_key, None)
            self._attr_is_on = _api_to_bool(val)
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def _write_with_pair(self, new_value: bool) -> None:
        """Write this toggle's value along with its paired toggle's current value."""
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        paired_val = "0"
        if settings:
            paired_raw = getattr(settings, self._paired_settings_key, None)
            paired_val = _bool_to_api(_api_to_bool(paired_raw))

        payload = {
            self._api_key: _bool_to_api(new_value),
            self._paired_api_key: paired_val,
        }
        _LOGGER.debug("Writing paired toggles for inverter %s: %s", self._sn, payload)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            payload,
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the timer."""
        await self._write_with_pair(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the timer."""
        await self._write_with_pair(False)


class SunSynkSimpleSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for simple boolean settings (use timer, energy mode)."""

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
        """Initialise the simple switch entity."""
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
        settings = get_inverter_settings(self.coordinator, self._plant_id, self._sn)
        self._attr_available = settings is not None
        if was_available and settings is None:
            _LOGGER.warning("Entity %s is now unavailable", self._attr_unique_id)
        if settings:
            val = getattr(settings, self._settings_key, None)
            self._attr_is_on = _api_to_bool(val)
        else:
            self._attr_is_on = None
        super()._handle_coordinator_update()

    async def _write_value(self, new_value: bool) -> None:
        """Write the setting value."""
        payload = {self._api_key: _bool_to_api(new_value)}
        _LOGGER.debug("Writing setting for inverter %s: %s", self._sn, payload)
        await async_write_settings(
            self._token_manager,
            self._region_idx,
            self._sn,
            payload,
            async_client=get_async_client(self.hass),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the setting."""
        await self._write_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the setting."""
        await self._write_value(False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SunSynk switch platform."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    token_manager = runtime.token_manager
    region_idx: int = entry.data["region"]

    if not coordinator.data:
        return

    entities: list[SwitchEntity] = []

    for plant_id, plant_data in coordinator.data.get("plants", {}).items():
        for sn, inv_data in plant_data.get("inverters", {}).items():
            if not inv_data.get("settings"):
                continue

            # Timer toggles (paired: time{N}on + genTime{N}on)
            for api_key, name, settings_key, paired_api, paired_sk in TIMER_TOGGLE_DEFS:
                entities.append(
                    SunSynkPairedTimerSwitch(
                        coordinator,
                        plant_id,
                        sn,
                        api_key,
                        name,
                        settings_key,
                        paired_api,
                        paired_sk,
                        token_manager,
                        region_idx,
                    )
                )

            # Gen timer toggles (paired: genTime{N}on + time{N}on)
            for (
                api_key,
                name,
                settings_key,
                paired_api,
                paired_sk,
            ) in GEN_TIMER_TOGGLE_DEFS:
                entities.append(
                    SunSynkPairedTimerSwitch(
                        coordinator,
                        plant_id,
                        sn,
                        api_key,
                        name,
                        settings_key,
                        paired_api,
                        paired_sk,
                        token_manager,
                        region_idx,
                    )
                )

            # Simple toggles (use timer, energy mode)
            for api_key, name, settings_key in SIMPLE_TOGGLE_DEFS:
                entities.append(
                    SunSynkSimpleSwitch(
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

    async_add_entities(entities)
