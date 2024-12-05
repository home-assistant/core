import logging

from homeassistant.components.camera import CameraEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseCameraDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("camera")
    if entities is not None:
      async_add_entities(SynapseCamera(hass, bridge, entity) for entity in entities)

class SynapseCamera(SynapseBaseEntity, CameraEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseCameraDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def brand(self):
        return self.entity.get("brand")

    @property
    def frame_interval(self):
        return self.entity.get("frame_interval")

    @property
    def frontend_stream_type(self):
        return self.entity.get("frontend_stream_type")

    @property
    def is_on(self):
        return self.entity.get("is_on")

    @property
    def is_recording(self):
        return self.entity.get("is_recording")

    @property
    def is_streaming(self):
        return self.entity.get("is_streaming")

    @property
    def model(self):
        return self.entity.get("model")

    @property
    def motion_detection_enabled(self):
        return self.entity.get("motion_detection_enabled")

    @property
    def use_stream_for_stills(self):
        return self.entity.get("use_stream_for_stills")

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_enable_motion_detection(self, **kwargs) -> None:
        """Enable motion detection."""
        self.hass.bus.async_fire(
            self.bridge.event_name("enable_motion_detection"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_disable_motion_detection(self, **kwargs) -> None:
        """Disable motion detection."""
        self.hass.bus.async_fire(
            self.bridge.event_name("disable_motion_detection"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
