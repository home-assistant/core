"""Number platform for KEBA P40 (charging current limit)."""

from keba_kecontact_p40 import KebaP40Error

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import KebaP40ConfigEntry
from .entity import KebaP40Entity

PARALLEL_UPDATES = 1

DEFAULT_MIN_CURRENT = 6.0
DEFAULT_MAX_CURRENT = 16.0

CURRENT_LIMIT = NumberEntityDescription(
    key="charging_current_limit",
    translation_key="charging_current_limit",
    device_class=NumberDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    native_step=1,
    mode=NumberMode.SLIDER,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 current-limit number."""
    async_add_entities([KebaP40CurrentLimit(entry.runtime_data, CURRENT_LIMIT)])


class KebaP40CurrentLimit(KebaP40Entity, NumberEntity):
    """Number entity to set the chargepoint max current."""

    @property
    def native_min_value(self) -> float:
        """Return the minimum selectable current in A."""
        value = self.coordinator.data.load_management.min_default_current_ma
        return DEFAULT_MIN_CURRENT if value is None else value / 1000

    @property
    def native_max_value(self) -> float:
        """Return the maximum selectable current in A."""
        value = self.coordinator.data.load_management.max_available_current_ma
        return DEFAULT_MAX_CURRENT if value is None else value / 1000

    @property
    def native_value(self) -> float | None:
        """Return the currently offered current in A."""
        meter = self._wallbox.meter
        if meter is None or meter.current_offered_ma is None:
            return None
        return meter.current_offered_ma / 1000

    async def async_set_native_value(self, value: float) -> None:
        """Set the chargepoint max current."""
        try:
            await self.coordinator.client.set_max_current(int(value * 1000))
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()
