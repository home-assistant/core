"""The Aprilaire number component."""

from __future__ import annotations

from typing import cast

from pyaprilaire.const import Attribute

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AprilaireCoordinator
from .entity import BaseAprilaireEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aprilaire number devices."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.unique_id]

    assert config_entry.unique_id is not None

    entities = []

    if coordinator.data.get(Attribute.DEHUMIDIFICATION_AVAILABLE) == 1:
        entities.append(
            AprilaireDehumidificationSetpointEntity(coordinator, config_entry.unique_id)
        )

    async_add_entities(entities)


class AprilaireDehumidificationSetpointEntity(BaseAprilaireEntity, NumberEntity):
    """Aprilaire dehumidification setpoint entity."""

    _attr_translation_key = "dehumidification_setpoint"
    _attr_icon = "mdr:water-percent"
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        """Get the current dehumidification setpoint value."""

        return cast(
            float, self.coordinator.data.get(Attribute.DEHUMIDIFICATION_SETPOINT)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the dehumidification setpoint."""

        await self.coordinator.client.set_dehumidification_setpoint(int(value))
