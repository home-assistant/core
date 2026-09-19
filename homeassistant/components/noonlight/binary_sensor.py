"""Binary sensor for Noonlight API reachability."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .entity import NoonlightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoonlightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Noonlight binary sensor."""
    async_add_entities([NoonlightApiReachable(entry.runtime_data)])


class NoonlightApiReachable(NoonlightEntity, BinarySensorEntity):
    """``on`` while the Noonlight API is reachable and the token is valid.

    CONNECTIVITY device class: ``on`` == connected. Build automations on this
    to be warned of a broken token or network problem ahead of time.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the API reachable binary sensor."""
        super().__init__(coordinator, "api_reachable")

    @property
    def is_on(self) -> bool:
        """Return True while the Noonlight API is reachable and authenticated."""
        return self.coordinator.data
