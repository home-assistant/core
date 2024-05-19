"""Event module."""

from deebot_client.capabilities import Capabilities, CapabilityEvent, VacuumCapabilities
from deebot_client.device import Device
from deebot_client.events import CleanJobStatus, PositionsEvent, ReportStatsEvent

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcovacsConfigEntry
from .const import POSITIONS_UPDATED_EVENT
from .entity import EcovacsEntity
from .util import get_name_key


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity] = []
    entities.extend(
        EcovacsLastJobEventEntity(device) for device in controller.devices(Capabilities)
    )
    entities.extend(
        EcovacsLastPositionEventEntity(device)
        for device in controller.devices(VacuumCapabilities)
        if device.capabilities.map and device.capabilities.map.position
    )
    async_add_entities(entities)


class EcovacsLastJobEventEntity(
    EcovacsEntity[Capabilities, CapabilityEvent[ReportStatsEvent]],
    EventEntity,
):
    """Ecovacs last job event entity."""

    entity_description = EventEntityDescription(
        key="stats_report",
        translation_key="last_job",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=["finished", "finished_with_warnings", "manually_stopped"],
    )

    def __init__(self, device: Device[Capabilities]) -> None:
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


class EcovacsLastPositionEventEntity(
    EcovacsEntity[VacuumCapabilities, CapabilityEvent[PositionsEvent]],
    EventEntity,
):
    """Ecovacs last job event entity."""

    entity_description = EventEntityDescription(
        key="last_position",
        translation_key="last_position",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=[POSITIONS_UPDATED_EVENT],
    )

    def __init__(self, device: Device[VacuumCapabilities]) -> None:
        """Initialize entity."""
        super().__init__(device, device.capabilities.map.position)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: PositionsEvent) -> None:
            """Handle event."""
            event_data: dict[str, dict] = {
                position.type.name.lower(): {
                    "x": position.x,
                    "y": position.y,
                }
                for position in event.positions
            }
            self._trigger_event(POSITIONS_UPDATED_EVENT, event_data)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)
