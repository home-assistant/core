import logging  # noqa: D100, EXE002

from homeassistant.components.group import (
    DOMAIN as GROUP_DOMAIN,  # type: ignore  # noqa: PGH003
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from .sensor import VirtualPowerSensor

_LOGGER = logging.getLogger(__name__)


class DeviceClassGroupSync:
    """Custom integration class to sync devices by device_class into a group."""

    def __init__(self, hass, group_name, device_class) -> None:
        """Initialize the class with the Home Assistant instance."""
        self.hass = hass
        self.group_name = group_name
        self.device_class = device_class

    async def find_and_sync_devices(self) -> None:
        """Find all devices by device_class and sync them into a group."""
        # Get all states from Home Assistant
        all_entities = self.hass.states.async_all()

        # Filter entities by device_class
        matching_entities = [
            entity.entity_id
            for entity in all_entities
            if (
                entity.attributes.get("device_class") == self.device_class
                and "group_sensor" not in entity.entity_id
            )
        ]

        # Use the group.set service to create or update the group
        await self.hass.services.async_call(
            GROUP_DOMAIN,
            "set",
            {
                "object_id": self.group_name,
                "name": f"{self.device_class} Group",
                "entities": matching_entities,
            },
        )

        _LOGGER.debug(
            f"Synced {len(matching_entities)} entities to group {self.group_name}"  # noqa: G004
        )


# Example usage inside your custom integration
async def async_setup_devicegroup(hass) -> bool:
    """Set up the integration."""

    # Initialize the group sync for 'smoke' device_class
    smokealarm_sync = DeviceClassGroupSync(hass, "smokealarm_sensors_group", "smoke")
    await smokealarm_sync.find_and_sync_devices()

    # Initialize the group sync for 'carbon_monoxide' device_class
    carbon_monoxide_sync = DeviceClassGroupSync(
        hass, "carbon_monoxide_sensors_group", "carbon_monoxide"
    )
    await carbon_monoxide_sync.find_and_sync_devices()

    # Initialize the group sync for 'door' device_class
    door_sync = DeviceClassGroupSync(hass, "door_sensors_group", "door")
    await door_sync.find_and_sync_devices()

    # Initialize the group sync for 'window' device_class
    window_sync = DeviceClassGroupSync(hass, "window_sensors_group", "window")
    await window_sync.find_and_sync_devices()

    # Initialize the group sync for 'moisture' device_class
    moisture_sync = DeviceClassGroupSync(hass, "moisture_sensors_group", "moisture")
    await moisture_sync.find_and_sync_devices()

    # Initialize the group sync for 'sound' device_class
    sound_sync = DeviceClassGroupSync(hass, "sound_sensors_group", "sound")
    await sound_sync.find_and_sync_devices()

    # Initialize the group sync for 'vibration' device_class
    vibration_sync = DeviceClassGroupSync(hass, "vibration_sensors_group", "vibration")
    await vibration_sync.find_and_sync_devices()

    # Initialize the group sync for 'humidity' device_class
    humidity_sync = DeviceClassGroupSync(hass, "humidity_sensors_group", "humidity")
    await humidity_sync.find_and_sync_devices()

    # Initialize the group sync for 'temperature' device_class
    temperature_sync = DeviceClassGroupSync(
        hass, "temperature_sensors_group", "temperature"
    )
    await temperature_sync.find_and_sync_devices()

    return True
