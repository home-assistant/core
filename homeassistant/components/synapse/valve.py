import logging

from homeassistant.components.valve import ValveEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseValveDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("valve")
    if entities is not None:
      async_add_entities(SynapseValve(hass, bridge, entity) for entity in entities)

class SynapseValve(SynapseBaseEntity, ValveEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseValveDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def current_valve_position(self):
        return self.entity.get("current_valve_position")

    @property
    def is_closed(self):
        return self.entity.get("is_closed")

    @property
    def is_opening(self):
        return self.entity.get("is_opening")

    @property
    def reports_position(self):
        return self.entity.get("reports_position")

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @property
    def is_closing(self):
        return self.entity.get("is_closing")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_open_valve(self, **kwargs) -> None:
        """Proxy the request to open the valve."""
        self.hass.bus.async_fire(
            self.bridge.event_name("open_valve"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_close_valve(self, **kwargs) -> None:
        """Proxy the request to close the valve."""
        self.hass.bus.async_fire(
            self.bridge.event_name("close_valve"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_set_valve_position(self, position: float, **kwargs) -> None:
        """Proxy the request to set the valve position."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_valve_position"),
            {"unique_id": self.entity.get("unique_id"), "position": position, **kwargs},
        )

    @callback
    async def async_stop_valve(self, **kwargs) -> None:
        """Proxy the request to stop the valve."""
        self.hass.bus.async_fire(
            self.bridge.event_name("stop_valve"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
