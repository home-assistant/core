"""Alarm control panels on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from zigpy.zcl.clusters.security import IasAce

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.cluster_handlers.security import (
    SIGNAL_ALARM_TRIGGERED,
    SIGNAL_ARMED_STATE_CHANGED,
    IasAceClusterHandler,
)
from .core.const import (
    CLUSTER_HANDLER_IAS_ACE,
    CONF_ALARM_ARM_REQUIRES_CODE,
    CONF_ALARM_FAILED_TRIES,
    CONF_ALARM_MASTER_CODE,
    SIGNAL_ADD_ENTITIES,
    ZHA_ALARM_OPTIONS,
)
from .core.helpers import async_get_zha_config_value, get_zha_data
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.device import ZHADevice

STRICT_MATCH = functools.partial(
    ZHA_ENTITIES.strict_match, Platform.ALARM_CONTROL_PANEL
)

IAS_ACE_STATE_MAP = {
    IasAce.PanelStatus.Panel_Disarmed: STATE_ALARM_DISARMED,
    IasAce.PanelStatus.Armed_Stay: STATE_ALARM_ARMED_HOME,
    IasAce.PanelStatus.Armed_Night: STATE_ALARM_ARMED_NIGHT,
    IasAce.PanelStatus.Armed_Away: STATE_ALARM_ARMED_AWAY,
    IasAce.PanelStatus.In_Alarm: STATE_ALARM_TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation alarm control panel from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.ALARM_CONTROL_PANEL]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_IAS_ACE)
class ZHAAlarmControlPanel(ZhaEntity, AlarmControlPanelEntity):
    """Entity for ZHA alarm control devices."""

    _attr_translation_key: str = "alarm_control_panel"
    _attr_code_format = CodeFormat.TEXT
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(
        self, unique_id, zha_device: ZHADevice, cluster_handlers, **kwargs
    ) -> None:
        """Initialize the ZHA alarm control device."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        cfg_entry = zha_device.gateway.config_entry
        self._cluster_handler: IasAceClusterHandler = cluster_handlers[0]
        self._cluster_handler.panel_code = async_get_zha_config_value(
            cfg_entry, ZHA_ALARM_OPTIONS, CONF_ALARM_MASTER_CODE, "1234"
        )
        self._cluster_handler.code_required_arm_actions = async_get_zha_config_value(
            cfg_entry, ZHA_ALARM_OPTIONS, CONF_ALARM_ARM_REQUIRES_CODE, False
        )
        self._cluster_handler.max_invalid_tries = async_get_zha_config_value(
            cfg_entry, ZHA_ALARM_OPTIONS, CONF_ALARM_FAILED_TRIES, 3
        )

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ARMED_STATE_CHANGED, self.async_set_armed_mode
        )
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ALARM_TRIGGERED, self.async_alarm_trigger
        )

    @callback
    def async_set_armed_mode(self) -> None:
        """Set the entity state."""
        self.async_write_ha_state()

    @property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._cluster_handler.code_required_arm_actions

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._cluster_handler.arm(IasAce.ArmMode.Disarm, code, 0)
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._cluster_handler.arm(IasAce.ArmMode.Arm_Day_Home_Only, code, 0)
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._cluster_handler.arm(IasAce.ArmMode.Arm_All_Zones, code, 0)
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._cluster_handler.arm(IasAce.ArmMode.Arm_Night_Sleep_Only, code, 0)
        self.async_write_ha_state()

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        self.async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return IAS_ACE_STATE_MAP.get(self._cluster_handler.armed_state)
