"""Event module."""

from deebot_client.capabilities import CapabilityEvent
from deebot_client.device import Device
from deebot_client.events import CleanJobStatus, ReportStatsEvent

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsEntity
from .util import get_name_key


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    async_add_entities(
        EcovacsLastJobEventEntity(device) for device in controller.devices
    )


class EcovacsLastJobEventEntity(
    EcovacsEntity[CapabilityEvent[ReportStatsEvent]],
    EventEntity,
):
    """Ecovacs last job event entity."""

    entity_description = EventEntityDescription(
        key="stats_report",
        translation_key="last_job",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=["finished", "finished_with_warnings", "manually_stopped"],
    )

    def __init__(self, device: Device) -> None:
        """Initialize entity."""
        super().__init__(device, device.capabilities.stats.report)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: ReportStatsEvent) -> None:
            """Handle event."""
            if event.status in (CleanJobStatus.NO_STATUS, CleanJobStatus.CLEANING):
                # we trigger only on job done
                return

            event_type = get_name_key(event.status)
            self._trigger_event(event_type)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)
