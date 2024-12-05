from .bridge import SynapseBridge
from .const import DOMAIN, SynapseCoverDefinition

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.cover import CoverEntity
import logging




async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("cover")
    if entities is not None:
      async_add_entities(SynapseCover(hass, bridge, entity) for entity in entities)


class SynapseCover(CoverEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseCoverDefinition,
    ):
        self.hass = hass
        self.bridge = hub
        self.entity = entity
        self.logger = logging.getLogger(__name__)
        self._listen()

    # common to all
    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        declared = self.entity.get("device_id", "")
        if len(declared) > 0:
            return self.bridge.device_list[declared]
        return self.bridge.device

    @property
    def unique_id(self):
        return self.entity.get("unique_id")

    @property
    def suggested_object_id(self):
        return self.entity.get("suggested_object_id")

    @property
    def translation_key(self):
        return self.entity.get("translation_key")

    @property
    def icon(self):
        return self.entity.get("icon")

    @property
    def extra_state_attributes(self):
        return self.entity.get("attributes") or {}

    @property
    def entity_category(self):
        if self.entity.get("entity_category") == "config":
            return EntityCategory.CONFIG
        if self.entity.get("entity_category") == "diagnostic":
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def name(self):
        return self.entity.get("name")

    @property
    def suggested_area_id(self):
        return self.entity.get("area_id")

    @property
    def labels(self):
        return self.entity.get("labels")

    @property
    def available(self):
        return self.bridge.connected()

    # domain specific
    @property
    def current_cover_position(self):
        return self.entity.get("current_cover_position")

    @property
    def current_cover_tilt_position(self):
        return self.entity.get("current_cover_tilt_position")

    @property
    def is_closed(self):
        return self.entity.get("is_closed")

    @property
    def is_closing(self):
        return self.entity.get("is_closing")

    @property
    def is_opening(self):
        return self.entity.get("is_opening")

    @callback
    async def async_stop_cover_tilt(self, **kwargs) -> None:
        """Proxy the request to stop cover tilt."""
        self.hass.bus.async_fire(
            self.bridge.event_name("stop_cover_tilt"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_set_cover_tilt_position(self, tilt_position: int, **kwargs) -> None:
        """Proxy the request to set cover tilt position."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_cover_tilt_position"),
            {
                "unique_id": self.entity.get("unique_id"),
                "tilt_position": tilt_position,
                **kwargs,
            },
        )

    @callback
    async def async_close_cover_tilt(self, **kwargs) -> None:
        """Proxy the request to close cover tilt."""
        self.hass.bus.async_fire(
            self.bridge.event_name("close_cover_tilt"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_open_cover_tilt(self, **kwargs) -> None:
        """Proxy the request to open cover tilt."""
        self.hass.bus.async_fire(
            self.bridge.event_name("open_cover_tilt"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_stop_cover(self, **kwargs) -> None:
        """Proxy the request to stop cover."""
        self.hass.bus.async_fire(
            self.bridge.event_name("stop_cover"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_set_cover_position(self, position: int, **kwargs) -> None:
        """Proxy the request to set cover position."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_cover_position"),
            {"unique_id": self.entity.get("unique_id"), "position": position, **kwargs},
        )

    @callback
    async def async_close_cover(self, **kwargs) -> None:
        """Proxy the request to close cover."""
        self.hass.bus.async_fire(
            self.bridge.event_name("close_cover"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_open_cover(self, **kwargs) -> None:
        """Proxy the request to open cover."""
        self.hass.bus.async_fire(
            self.bridge.event_name("open_cover"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    def _listen(self):
        self.async_on_remove(
            self.hass.bus.async_listen(
                self.bridge.event_name("update"),
                self._handle_entity_update,
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                self.bridge.event_name("health"),
                self._handle_availability_update,
            )
        )

    @callback
    def _handle_entity_update(self, event):
        if event.data.get("unique_id") == self.entity.get("unique_id"):
            self.entity = event.data.get("data")
            self.async_write_ha_state()

    @callback
    async def _handle_availability_update(self, event):
        """Handle health status update."""
        self.async_schedule_update_ha_state(True)
