import logging

from homeassistant.components.waterheater import WaterHeaterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseWaterHeaterDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("water_heater")
    if entities is not None:
      async_add_entities(SynapseWaterHeater(hass, bridge, entity) for entity in entities)

class SynapseWaterHeater(SynapseBaseEntity, WaterHeaterEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseWaterHeaterDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def min_temp(self):
        return self.entity.get("min_temp")

    @property
    def max_temp(self):
        return self.entity.get("max_temp")

    @property
    def current_temperature(self):
        return self.entity.get("current_temperature")

    @property
    def target_temperature(self):
        return self.entity.get("target_temperature")

    @property
    def target_temperature_high(self):
        return self.entity.get("target_temperature_high")

    @property
    def target_temperature_low(self):
        return self.entity.get("target_temperature_low")

    @property
    def temperature_unit(self):
        return self.entity.get("temperature_unit")

    @property
    def current_operation(self):
        return self.entity.get("current_operation")

    @property
    def operation_list(self):
        return self.entity.get("operation_list")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @property
    def is_away_mode_on(self):
        return self.entity.get("is_away_mode_on")

    @callback
    async def async_set_temperature(self, temperature: float, **kwargs) -> None:
        """Proxy the request to set the temperature."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_temperature"),
            {
                "unique_id": self.entity.get("unique_id"),
                "temperature": temperature,
                **kwargs,
            },
        )

    @callback
    async def async_set_operation_mode(self, operation_mode: str, **kwargs) -> None:
        """Proxy the request to set the operation mode."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_operation_mode"),
            {
                "unique_id": self.entity.get("unique_id"),
                "operation_mode": operation_mode,
                **kwargs,
            },
        )

    @callback
    async def async_turn_away_mode_on(self, **kwargs) -> None:
        """Proxy the request to turn away mode on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_away_mode_on"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_away_mode_off(self, **kwargs) -> None:
        """Proxy the request to turn away mode off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_away_mode_off"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Proxy the request to turn the entity on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Proxy the request to turn the entity off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
