"""Abstract entity definitions."""

from homeassistant.helpers.entity import Entity, EntityDescription

from . import WatercrystConfigEntry


class WatercrystEntity(Entity):
    """An abstract class for WATERCryst entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, config_entry: WatercrystConfigEntry, entity_description: EntityDescription
    ) -> None:
        """Initialize a WatercrystEntity instance."""
        super().__init__()

        data = config_entry.runtime_data

        self._attr_device_info = data.device_info
        self._attr_unique_id = f"{data.bsn}_{entity_description.key}"

        self.entity_description = entity_description
        self.runtime_data = data

        self._client = config_entry.runtime_data.client
