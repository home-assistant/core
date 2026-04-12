"""Aquarite Select entities."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PUMP_MODE_OPTIONS: tuple[str, ...] = ("manual", "auto", "heat", "smart", "intel")
PUMP_SPEED_OPTIONS: tuple[str, ...] = ("slow", "medium", "high")
TIMER_SPEED_OPTIONS: tuple[str, ...] = ("slow", "medium", "high")

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    dataservice = entry.runtime_data
    pool_id, pool_name = dataservice.pool_id, entry.title

    entities = [
        AquariteSelectEntity(
            dataservice, pool_id, pool_name,
            "pump_mode", "filtration.mode", PUMP_MODE_OPTIONS,
        ),
        AquariteSelectEntity(
            dataservice, pool_id, pool_name,
            "pump_speed", "filtration.manVel", PUMP_SPEED_OPTIONS,
        ),
    ]

    for index in range(1, 4):
        entities.append(
            AquariteSelectEntity(
                dataservice, pool_id, pool_name,
                f"filtration_timer_speed_{index}",
                f"filtration.timerVel{index}",
                TIMER_SPEED_OPTIONS,
            )
        )

    async_add_entities(entities)


class AquariteSelectEntity(AquariteEntity, SelectEntity):
    """Aquarite select entity."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        translation_key: str,
        value_path: str,
        options: tuple[str, ...],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._options_map = options
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)
        self._attr_options = list(options)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        raw_value = self.coordinator.get_value(self._value_path)
        try:
            return self._options_map[int(raw_value)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            await self.coordinator.api.set_value(
                self._pool_id, self._value_path, self._options_map.index(option)
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
