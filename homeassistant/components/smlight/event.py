"""Event platform for SLZB-Ultima."""

from homeassistant.components.infrared import InfraredCommandEventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INFRARED_RECEIVER_UNIQUE_ID_SUFFIX
from .coordinator import SmConfigEntry, base_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the companion event entity of the SLZB-Ultima infrared receiver."""
    coordinator = entry.runtime_data.data

    if coordinator.data.info.has_peripherals:
        async_add_entities(
            [
                InfraredCommandEventEntity(
                    f"{coordinator.unique_id}{INFRARED_RECEIVER_UNIQUE_ID_SUFFIX}",
                    base_device_info(coordinator.data.info, coordinator.client.host),
                )
            ]
        )
