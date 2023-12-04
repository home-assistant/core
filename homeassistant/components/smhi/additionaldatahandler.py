"""Handles additional information such as warnings, fire risk."""
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get

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
        self.fire_risk_data: set[SmhiGeolocationEvent] = set()
        self.warning_data: set[SmhiGeolocationEvent] = set()
        self.lightning_data: set[SmhiGeolocationEvent] = set()
        self.weather_data: set[SmhiGeolocationEvent] = set()
        self.add_entity_callback: AddEntitiesCallback
        self.states = {
            "lightning": False,
            "warnings": False,
            "weather": False,
            "fire_risk": False,
        }
        self._initialized = True
        self.hass: Optional[HomeAssistant] = None

    async def get_additional_data(self) -> None:
        """Get additional data."""

        # Handle updating depending on state
        if self.states["warnings"]:
            await self.remove_old_entities("warnings")
            self.warning_data.clear()
            warnings = SmhiWarnings()
            new_warnings = await warnings.get_warnings()
            self.warning_data.update(new_warnings)

        if self.states["fire_risk"]:
            await self.remove_old_entities("fire_risk")
            self.fire_risk_data.clear()
            new_fire_risk_data = await get_grassfire_risk()
            self.fire_risk_data.update(new_fire_risk_data)

        if self.states["weather"]:
            await self.remove_old_entities("weather")
            self.weather_data.clear()
            weather_locations = SmhiWeatherLocations()
            new_weather_data = await weather_locations.get_weather_locations()
            self.weather_data.update(new_weather_data)

        if self.states["lightning"]:
            await self.remove_old_entities("lightning")
            self.lightning_data.clear()
            lightning = SmhiLightning()
            new_lightning_data = await lightning.get_lightning_impacts()
            self.lightning_data.update(new_lightning_data)

    def init_add_entities_callback(
        self, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize the callback for adding entities."""
        self.add_entity_callback = async_add_entities

    def init_add_hass_callback(self, hass: HomeAssistant) -> None:
        """Initialize the callback for removing entities."""
        self.hass = hass

    async def set_state(self, name: str, state: bool) -> None:
        """Setstate."""
        self.states[name] = state
        if name == "warnings" and not state:
            await self.remove_old_entities("warnings")
        elif name == "fire_risk" and not state:
            await self.remove_old_entities("fire_risk")
        elif name == "weather" and not state:
            await self.remove_old_entities("weather")
        elif name == "lightning" and not state:
            await self.remove_old_entities("lightning")

    async def remove_old_entities(self, tag: str = "") -> None:
        """Remove old entities."""

        if self.hass is None:
            return

        entity_registry = async_get(self.hass)

        tags_to_process = (
            [tag] if tag else ["warnings", "fire_risk", "weather", "lightning"]
        )

        for current_tag in tags_to_process:
            tag_prefix = f"weather.{current_tag}"

            # Filter entities based on the tag in their entity_id
            entities_to_remove = [
                entity_id
                for entity_id, entity in entity_registry.entities.items()
                if entity_id.startswith(tag_prefix)
            ]

            for entity_id in entities_to_remove:
                entity_registry.async_remove(entity_id)
