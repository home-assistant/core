import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseAlarmControlPanelDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("alarm_control_panel")
    if entities is not None:
      async_add_entities(SynapseAlarmControlPanel(hass, bridge, entity) for entity in entities)


class SynapseAlarmControlPanel(SynapseBaseEntity, AlarmControlPanelEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseAlarmControlPanelDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def changed_by(self):
        return self.entity.get("changed_by")

    @property
    def code_format(self):
        return self.entity.get("code_format")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @property
    def code_arm_required(self):
        return self.entity.get("code_arm_required")

    @callback
    async def async_arm_custom_bypass(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("arm_custom_bypass"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_trigger(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("trigger"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_arm_vacation(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("arm_vacation"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_arm_night(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("arm_night"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_arm_away(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("arm_away"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_arm_home(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("arm_home"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_alarm_disarm(self, **kwargs) -> None:
        self.hass.bus.async_fire(
            self.bridge.event_name("alarm_disarm"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_toggle(self, **kwargs) -> None:
        """Handle the number press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("toggle"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
