import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.vacuum import VacuumEntity

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseVacuumDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("vacuum")
    if entities is not None:
      async_add_entities(SynapseVacuum(hass, bridge, entity) for entity in entities)

class SynapseVacuum(SynapseBaseEntity, VacuumEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseVacuumDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def battery_level(self):
        return self.entity.get("battery_level")

    @property
    def fan_speed(self):
        return self.entity.get("fan_speed")

    @property
    def fan_speed_list(self):
        return self.entity.get("fan_speed_list")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_clean_spot(self, **kwargs) -> None:
        """Proxy the request to clean a spot."""
        self.hass.bus.async_fire(
            self.bridge.event_name("clean_spot"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_locate(self, **kwargs) -> None:
        """Proxy the request to locate."""
        self.hass.bus.async_fire(
            self.bridge.event_name("locate"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_pause(self, **kwargs) -> None:
        """Proxy the request to pause."""
        self.hass.bus.async_fire(
            self.bridge.event_name("pause"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_return_to_base(self, **kwargs) -> None:
        """Proxy the request to return to base."""
        self.hass.bus.async_fire(
            self.bridge.event_name("return_to_base"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_send_command(self, command: str, **kwargs) -> None:
        """Proxy the request to send a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("send_command"),
            {"unique_id": self.entity.get("unique_id"), "command": command, **kwargs},
        )

    @callback
    async def async_set_fan_speed(self, fan_speed: str, **kwargs) -> None:
        """Proxy the request to set fan speed."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_fan_speed"),
            {
                "unique_id": self.entity.get("unique_id"),
                "fan_speed": fan_speed,
                **kwargs,
            },
        )

    @callback
    async def async_start(self, **kwargs) -> None:
        """Proxy the request to start."""
        self.hass.bus.async_fire(
            self.bridge.event_name("start"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_stop(self, **kwargs) -> None:
        """Proxy the request to stop."""
        self.hass.bus.async_fire(
            self.bridge.event_name("stop"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
