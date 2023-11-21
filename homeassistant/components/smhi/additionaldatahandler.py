"""Handles additional information such as warnings, fire risk."""
from typing import Any, Optional

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .firerisk.fire_risk_data_fetcher import get_grassfire_risk
from .smhi_geolocation_event import SmhiGeolocationEvent
from .warnings import SmhiWarnings


class AdditionalDataHandler:
    """Class that handles additional information such as warnings, fire risk."""

    _instance: Optional["AdditionalDataHandler"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "AdditionalDataHandler":
        """Init method, following singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Init method."""
        self.fire_risk_data: list[SmhiGeolocationEvent] = []
        self.warning_data: list[SmhiGeolocationEvent] = []
        self.add_entity_callback: AddEntitiesCallback

    def remove_smhi_events(self, events: list[SmhiGeolocationEvent]) -> None:
        """Remove SMHI Geolocation Events from the provided list."""
        for event in events:
            event.remove_self()

    async def get_additional_data(self) -> None:
        """Get additional data."""
        self.remove_smhi_events(self.warning_data)
        warnings = SmhiWarnings()
        self.warning_data = await warnings.get_warnings()
        self.remove_smhi_events(self.fire_risk_data)
        self.fire_risk_data = await get_grassfire_risk()

    def init_add_entities_callback(
        self, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Initialize the callback for adding entities."""
        self.add_entity_callback = async_add_entities
