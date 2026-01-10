"""Support for EnOcean buttons."""

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.entity_properties import HomeAssistantEntityProperties
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.button import ButtonEntity
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

    for entity_id in gateway.button_entities:
        properties: HomeAssistantEntityProperties = gateway.button_entities[entity_id]
        async_add_entities(
            [
                EnOceanButton(
                    entity_id,
                    gateway=gateway,
                    entity_category=properties.entity_category,
                )
            ]
        )


class EnOceanButton(EnOceanEntity, ButtonEntity):
    """Representation of EnOcean buttons."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        entity_category: str | None = None,
    ) -> None:
        """Initialize the EnOcean button."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            entity_category=entity_category,
        )

    def press(self) -> None:
        """Press the EnOcean button."""
        self.gateway.press_button(self.enocean_entity_id)
