"""Handles additional information such as warnings, fire risk."""
from typing import Any, Optional

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .firerisk.fire_risk_data_fetcher import get_grassfire_risk
from .lightning_api import SmhiLightning
from .smhi_geolocation_event import SmhiGeolocationEvent
from .warnings import SmhiWarnings
from .weather_locations import SmhiWeatherLocations


class AdditionalDataHandler:
    """Class that handles additional information such as warnings, fire risk."""

    _instance: Optional["AdditionalDataHandler"] = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "AdditionalDataHandler":
        """Init method, following singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Init method."""
        if self._initialized:
            return
        self.fire_risk_data: list[SmhiGeolocationEvent] = []
        self.warning_data: list[SmhiGeolocationEvent] = []
        self.lightning_data: list[SmhiGeolocationEvent] = []
        self.weather_data: list[SmhiGeolocationEvent] = []
        self.add_entity_callback: AddEntitiesCallback
        self.states = {
            "lightning": False,
            "warnings": False,
            "weather": False,
            "fire_risk": False,
        }
        self._initialized = True

    def remove_smhi_events(self, events: list[SmhiGeolocationEvent]) -> None:
        """Remove SMHI Geolocation Events from the provided list."""
        for event in events:
            event.remove_self()

    async def get_additional_data(self) -> None:
        """Get additional data."""

        # Handle updating depending on state
        if self.states["warnings"]:
            self.remove_smhi_events(self.warning_data)
            warnings = SmhiWarnings()
            self.warning_data = await warnings.get_warnings()

        if self.states["fire_risk"]:
            self.remove_smhi_events(self.fire_risk_data)
            self.fire_risk_data = await get_grassfire_risk()

        if self.states["weather"]:
            self.remove_smhi_events(self.weather_data)
            weather_locations = SmhiWeatherLocations()
            self.weather_data = await weather_locations.get_weather_locations()

        if self.states["lightning"]:
            self.remove_smhi_events(self.lightning_data)
            lightning = SmhiLightning()
            self.lightning_data = (
                await lightning.async_get_lightning_impact_most_recent()
            )

    def init_add_entities_callback(
        self, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize the callback for adding entities."""
        self.add_entity_callback = async_add_entities

    def set_state(self, name: str, state: bool) -> None:
        """Setstate."""
        self.states[name] = state
        if name == "warnings" and not state:
            self.remove_smhi_events(self.warning_data)
        elif name == "fire_risk" and not state:
            self.remove_smhi_events(self.fire_risk_data)
        elif name == "weather" and not state:
            self.remove_smhi_events(self.weather_data)
        elif name == "lightning" and not state:
            self.remove_smhi_events(self.lightning_data)
