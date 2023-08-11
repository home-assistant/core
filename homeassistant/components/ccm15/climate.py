"""Climate device for CCM15 coordinator."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CCM15Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator: CCM15Coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for ac_device in coordinator.get_devices():
        entities.append(ac_device)
    async_add_entities(entities, True)
