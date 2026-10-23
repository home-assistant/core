"""Weather data preferences."""

from typing import NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


class WeatherDataPreferences(TypedDict):
    """Weather data preferences.

    A missing sensor key means the sensors are detected automatically. A rain
    gauge of None means the user turned it off.
    """

    weather_entities: list[str]
    excluded_weather_entities: list[str]
    rain_gauge_entity: NotRequired[str | None]
    air_quality_entities: NotRequired[list[str]]
    pollen_entities: NotRequired[list[str]]


class WeatherDataPreferencesUpdate(TypedDict, total=False):
    """Weather data preferences update."""

    weather_entities: list[str]
    excluded_weather_entities: list[str]
    rain_gauge_entity: str | None
    air_quality_entities: list[str]
    pollen_entities: list[str]


@singleton.singleton(f"{DOMAIN}_manager")
async def async_get_manager(hass: HomeAssistant) -> WeatherDataManager:
    """Return an initialized preferences manager."""
    manager = WeatherDataManager(hass)
    await manager.async_initialize()
    return manager


class WeatherDataManager:
    """Manage the weather data preferences."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self._store: storage.Store[WeatherDataPreferences] = storage.Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self.data: WeatherDataPreferences = self.default_preferences()

    async def async_initialize(self) -> None:
        """Load the stored preferences."""
        if (data := await self._store.async_load()) is not None:
            self.data = data

    @staticmethod
    def default_preferences() -> WeatherDataPreferences:
        """Return the default preferences."""
        return {"weather_entities": [], "excluded_weather_entities": []}

    def async_update(self, update: WeatherDataPreferencesUpdate) -> None:
        """Update the preferences."""
        data = self.data.copy()
        data.update(update)
        self.data = data
        self._store.async_delay_save(lambda: data, 10)
