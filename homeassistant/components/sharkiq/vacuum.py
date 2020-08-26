"""Shark IQ robot vacuums."""
import logging
from typing import TYPE_CHECKING, Iterable

from .const import DOMAIN
from .sharkiq import SharkVacuumEntity
from .update_coordinator import SharkIqUpdateCoordinator

if TYPE_CHECKING:
    from sharkiqpy import SharkIqVacuum


LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Shark IQ vacuum cleaner."""
    coordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]  # type: SharkIqUpdateCoordinator
    devices: Iterable["SharkIqVacuum"] = coordinator.shark_vacs.values()
    device_names = [d.name for d in devices]
    LOGGER.debug(
        "Found %d Shark IQ device(s): %s",
        len(device_names),
        ", ".join([d.name for d in devices]),
    )
    async_add_entities([SharkVacuumEntity(d, coordinator) for d in devices])
