"""Binary sensor platform for the ENGIE Belgium integration."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION
from .coordinator import BRUSSELS_TIME_ZONE, EngieBeEpexCoordinator, epex_day_available

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EPEX binary sensors for dynamic-tariff households."""
    runtime_data = entry.runtime_data
    known_bans: set[str] = set()

    @callback
    def _async_add_tomorrow_available_sensors() -> None:
        """Add the tomorrow-available binary sensors for the dynamic households."""
        if (epex := runtime_data.epex) is None:
            return
        new_bans = [
            ban
            for ban, household in runtime_data.households.items()
            if household.is_dynamic and ban not in known_bans
        ]
        if not new_bans:
            return
        known_bans.update(new_bans)
        async_add_entities(
            EngieBeEpexTomorrowAvailableSensor(
                epex,
                ban=ban,
                device_info=runtime_data.households[ban].prices.device_info,
            )
            for ban in new_bans
        )

    runtime_data.epex_ready_callbacks.append(_async_add_tomorrow_available_sensors)
    _async_add_tomorrow_available_sensors()


class EngieBeEpexTomorrowAvailableSensor(
    CoordinatorEntity[EngieBeEpexCoordinator], BinarySensorEntity
):
    """Binary sensor that is on when tomorrow's EPEX prices are available."""

    _attr_attribution = ATTRIBUTION
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "epex_tomorrow_available"

    def __init__(
        self,
        coordinator: EngieBeEpexCoordinator,
        *,
        ban: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the tomorrow-available binary sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{ban}_epex_tomorrow_available"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when both granularities have slots for tomorrow."""
        tomorrow = dt_util.now(BRUSSELS_TIME_ZONE).date() + timedelta(days=1)
        return epex_day_available(self.coordinator.data, tomorrow)
