"""Support for TheSilentWave sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TheSilentWaveCoordinator, TheSilentWaveConfigEntry
from .entity import TheSilentWaveEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TheSilentWaveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([TheSilentWaveBinarySensor(coordinator, entry.entry_id)])


class TheSilentWaveBinarySensor(TheSilentWaveEntity, BinarySensorEntity):
    """Representation of a TheSilentWave binary sensor."""

    _attr_translation_key = "status"
    _attr_name = None  # Set to None to use device name as this is the main sensor

    def __init__(self, coordinator: TheSilentWaveCoordinator, entry_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry_id)
        # Set a more specific unique_id for this sensor entity
        self._attr_unique_id = f"{entry_id}_status"
        self._subscription_active = False

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        # Convert the coordinator data to a boolean state
        return self.coordinator.data.get("status") == "on"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Listen for coordinator updates to retry event subscription if needed
        @callback
        def _update_listener():
            """Handle updated data from the coordinator."""
            # Try subscribing to events if connection becomes available
            if (
                self.coordinator.has_connection
                and not self._subscription_active
                and hasattr(self.coordinator.client, "subscribe_to_events")
            ):
                self.hass.async_create_task(self._subscribe_to_events())

        # Register our listener
        self.async_on_remove(self.coordinator.async_add_listener(_update_listener))

        # Also try subscribing immediately
        # Only subscribe to events if we have a connection to the device
        if self.coordinator.has_connection and hasattr(
            self.coordinator.client, "subscribe_to_events"
        ):
            await self._subscribe_to_events()

    async def _subscribe_to_events(self) -> None:
        """Subscribe to device events."""
        if self._subscription_active:
            return

        try:
            unsubscribe_callback = await self.coordinator.client.subscribe_to_events(
                self.async_write_ha_state
            )
            self._subscription_active = True
            self.async_on_remove(
                lambda: self._handle_unsubscribe(unsubscribe_callback)
            )
        except Exception:
            # If subscription fails, we'll retry on the next coordinator update
            self._subscription_active = False

    def _handle_unsubscribe(self, unsubscribe_callback) -> None:
        """Handle unsubscription from events."""
        self._subscription_active = False
        unsubscribe_callback()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events when entity is removed."""
        self._subscription_active = False
        await super().async_will_remove_from_hass()
