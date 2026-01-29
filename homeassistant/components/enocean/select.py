"""Support for EnOcean buttons."""

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.entity_properties import HomeAssistantEntityProperties
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.select import SelectEntity
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

    for entity_id in gateway.select_entities:
        properties: HomeAssistantEntityProperties = gateway.select_entities[entity_id]
        async_add_entities(
            [
                EnOceanSelect(
                    entity_id,
                    gateway=gateway,
                    entity_category=properties.entity_category,
                    options=properties.options,
                    current_option=properties.current_option,
                )
            ]
        )


class EnOceanSelect(EnOceanEntity, SelectEntity):
    """Representation of EnOcean select."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        entity_category: str | None = None,
        options: list[str] | None = None,
        current_option: str | None = None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            entity_category=entity_category,
        )
        self._attr_options = options or []
        self._attr_current_option = current_option

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self.gateway.select_option(self.enocean_entity_id, option)
        self._attr_current_option = option
        self.schedule_update_ha_state()
