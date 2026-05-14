from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MertikConfigEntry
from .coordinator import MertikDataCoordinator
from .entity import MertikEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MertikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    dataservice = entry.runtime_data
    async_add_entities(
        [
            MertikFlameHeightEntity(dataservice, entry.entry_id, entry.data["name"]),
        ]
    )


class MertikFlameHeightEntity(MertikEntity, NumberEntity):
    """Flame height control (1-13 steps).

    Step 13 is the maximum (raw 0xFF), matching the device's own reporting.
    Flame height is shown as 0 when the fire is off (device ignores
    flame height commands when not running.
    """

    _attr_translation_key = "flame_height"
    _attr_icon = "mdi:fire"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 13
    _attr_native_step = 1

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-FlameHeight"

    # native_value returns 0 when the fire is off so the entity always shows
    # a number rather than 'unknown'. CoordinatorEntity still marks it
    # unavailable if the coordinator poll fails (connection lost).

    @property
    def native_value(self) -> float:
        return self._dataservice.get_flame_height()

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(
            self._dataservice.set_flame_height, int(value)
        )
        self._dataservice.async_set_updated_data(None)
