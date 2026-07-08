"""Music Assistant Sensor platform."""

from datetime import datetime
from typing import override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.errors import MusicAssistantError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import MusicAssistantConfigEntry
from .const import LOGGER, PARTY_URL_POLL_INTERVAL
from .entity import MusicAssistantPartyModeEntity


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
                        icon="mdi:link",
                    ),
                )
            ]
        )

    entry.runtime_data.party_handlers.setdefault(Platform.SENSOR, add_party_mode)


class MusicAssistantPartyModeSensor(MusicAssistantPartyModeEntity, SensorEntity):
    """Representation of a Sensor entity for Party Mode URL."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(mass, instance_id, unique_id_suffix=entity_description.key)
        self.entity_description = entity_description

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_timer,
                PARTY_URL_POLL_INTERVAL,
            )
        )

    async def _handle_timer(self, _now: datetime) -> None:
        """Handle periodic update."""
        await self.async_on_update()
        self.async_write_ha_state()

    @override
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
