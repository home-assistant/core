"""Aquarite Time entities for filtration interval control."""
from __future__ import annotations

import datetime

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite time entities."""
    dataservice = entry.runtime_data
    pool_id, pool_name = dataservice.pool_id, entry.title

    entities: list[AquariteTimeEntity] = []

    for translation_key, path in (
        ("filtration_interval_1_from", "filtration.interval1.from"),
        ("filtration_interval_1_to", "filtration.interval1.to"),
        ("filtration_interval_2_from", "filtration.interval2.from"),
        ("filtration_interval_2_to", "filtration.interval2.to"),
        ("filtration_interval_3_from", "filtration.interval3.from"),
        ("filtration_interval_3_to", "filtration.interval3.to"),
    ):
        entities.append(
            AquariteTimeEntity(
                dataservice, pool_id, pool_name, translation_key, path,
            )
        )

    async_add_entities(entities)


class AquariteTimeEntity(AquariteEntity, TimeEntity):
    """Time entity for filtration interval from/to values."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> datetime.time | None:
        """Return the interval time as a time object."""
        raw_value = self.coordinator.get_value(self._value_path)
        try:
            seconds = int(raw_value)
            hours = (seconds // 3600) % 24
            minutes = (seconds % 3600) // 60
            return datetime.time(hours, minutes)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: datetime.time) -> None:
        """Set the interval time."""
        seconds = value.hour * 3600 + value.minute * 60
        try:
            await self.coordinator.api.set_value(
                self._pool_id, self._value_path, seconds,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
