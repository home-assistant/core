"""Shark IQ robot vacuums."""
import logging
from typing import TYPE_CHECKING, List

from .const import DOMAIN, SHARKIQ_SESSION
from .sharkiq import SharkVacuumEntity

if TYPE_CHECKING:
    from sharkiqpy import AylaApi, SharkIqVacuum


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Shark IQ vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    ayla_api = domain_data[SHARKIQ_SESSION]  # type: AylaApi

    devices = await ayla_api.async_get_devices()  # type: List[SharkIqVacuum]
    device_names = ", ".join([d.name for d in devices])
    _LOGGER.debug("Found %d Shark IQ device(s): %s", len(devices), device_names)
    async_add_entities([SharkVacuumEntity(d) for d in devices], True)
