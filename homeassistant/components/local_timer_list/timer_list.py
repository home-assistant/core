"""Local timer list platform."""

from homeassistant.components.timer_list import TimerListEntity, TimerListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TIMER_LIST_NAME


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the local timer list entity from a config entry."""
    async_add_entities([LocalTimerListEntity(config_entry)])


class LocalTimerListEntity(TimerListEntity):
    """A local, in-memory timer list."""

    _attr_supported_features = (
        TimerListEntityFeature.START_TIMER
        | TimerListEntityFeature.PAUSE_TIMER
        | TimerListEntityFeature.CANCEL_TIMER
        | TimerListEntityFeature.ADD_TIME
    )

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._attr_name = config_entry.data[CONF_TIMER_LIST_NAME]
        self._attr_unique_id = config_entry.entry_id
