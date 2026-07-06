"""Music Assistant Sensor platform."""

from __future__ import annotations

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType
from music_assistant_models.errors import MusicAssistantError
from music_assistant_models.event import MassEvent

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Sensor Entities."""
    mass = entry.runtime_data.mass

    def add_party_mode(instance_id: str) -> None:
        """Handle add party mode."""
        async_add_entities(
            [
                MusicAssistantPartyModeSensor(
                    mass,
                    instance_id,
                    entity_description=SensorEntityDescription(
                        key="party_mode_url",
                        translation_key="party_mode_url",
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                )
            ]
        )

    entry.runtime_data.party_handlers.setdefault(Platform.SENSOR, add_party_mode)


class MusicAssistantPartyModeSensor(SensorEntity):
    """Representation of a Sensor entity for Party Mode URL."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        self.mass = mass
        self.instance_id = instance_id
        self.entity_description = entity_description
        
        provider = self.mass.get_provider(instance_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id)},
            name=provider.name if provider else "Party Mode",
            manufacturer="Music Assistant",
        )
        self._attr_unique_id = f"{instance_id}_{entity_description.key}"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.PROVIDERS_UPDATED,
            )
        )

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        await self.async_on_update()
        self.async_write_ha_state()

    async def async_on_update(self) -> None:
        """Handle provider updates."""
        try:
            url = await self.mass.send_command("party/url")
            self._attr_native_value = url
            self._attr_available = True
        except MusicAssistantError as err:
            LOGGER.debug("Failed to fetch party URL: %s", err)
            self._attr_native_value = None
            self._attr_available = False
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Unexpected error fetching party URL: %s", err)
            self._attr_native_value = None
            self._attr_available = False
