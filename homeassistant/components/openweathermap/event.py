"""OpenWeatherMap event entity."""

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN, ENTRY_NAME, ENTRY_WEATHER_COORDINATOR
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
  """Set up the OpenWeatherMap event platform."""
  coordinator: WeatherUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
      ENTRY_WEATHER_COORDINATOR
  ]

  async_add_entities([OpenWeatherMapEvent(coordinator)], False)


class OpenWeatherMapEvent(EventEntity):
  """OpenWeatherMap event entity."""

  _attr_name = "National weather alert issued"
  _attr_has_entity_name = True

  def __init__(self, coordinator: WeatherUpdateCoordinator):
    """Initialize the OpenWeatherMap event."""
    self._coordinator = coordinator
    

  @property
  def unique_id(self) -> str:
    """Return a unique ID."""
    return ENTRY_NAME

  @property
  def device_info(self):
    """Return device information about this entity."""
    return {
        "identifiers": {(DOMAIN, ENTRY_NAME)},
        "name": ENTRY_NAME,
        "manufacturer": "OpenWeatherMap",
    }

  @property
  def state(self) -> str:
    """Return the state of the entity."""
    return self._coordinator.data.get("event")

  @property
  def device_state_attributes(self) -> dict:
    """Return the state attributes of the entity."""
    return {
        "attribution": ATTRIBUTION,
        "event": self._coordinator.data.get("event"),
        "event_code": self._coordinator.data.get("event_code"),
        "event_description": self._coordinator.data.get("event_description"),
        "event_type": self._coordinator.data.get("event_type"),
    }

  @property
  def icon(self) -> str:
    """Return the icon of the entity."""
    return "mdi:calendar-star"

  @property
  def available(self) -> bool:
    """Return True if entity is available."""
    return self._coordinator.last_update_success
