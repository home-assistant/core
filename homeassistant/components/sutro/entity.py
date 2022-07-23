"""SutroEntity class."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class SutroEntity(CoordinatorEntity):
    """Representation of a Sutro Entity."""

    def __init__(self, coordinator, config_entry):
        """Initialize the entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
