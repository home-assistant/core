"""Support for EnOcean numbers."""

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.entity_properties import HomeAssistantEntityProperties
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.number import RestoreNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.number_entities:
        properties: HomeAssistantEntityProperties = gateway.number_entities[entity_id]
        async_add_entities(
            [
                EnOceanNumber(
                    entity_id,
                    gateway=gateway,
                    entity_category=properties.entity_category,
                    native_min_value=properties.native_min_value,
                    native_max_value=properties.native_max_value,
                    native_step=properties.native_step,
                    native_value=properties.native_value,
                )
            ]
        )


class EnOceanNumber(EnOceanEntity, RestoreNumber):
    """Representation of an EnOcean number entity."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        entity_category: str | None = None,
        native_min_value: float | None = None,
        native_max_value: float | None = None,
        native_step: float | None = None,
        native_value: float | None = None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            entity_category=entity_category,
        )
        self._attr_native_min_value = native_min_value or 0.0
        self._attr_native_max_value = native_max_value or 100.0
        self._attr_native_step = native_step or 1.0
        self._attr_native_value = native_value or 0.0

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_number_data()) is not None:
            self.gateway.set_number_value(
                self.enocean_entity_id, last_state.native_value
            )
            self._attr_native_value = last_state.native_value

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.gateway.set_number_value(self.enocean_entity_id, value)
        self._attr_native_value = value
        self.schedule_update_ha_state()
