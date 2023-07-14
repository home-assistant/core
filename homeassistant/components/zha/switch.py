"""Switches on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import Self
import zigpy.exceptions
from zigpy.zcl.clusters.general import OnOff
from zigpy.zcl.foundation import Status

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, EntityCategory, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_BASIC,
    CLUSTER_HANDLER_INOVELLI,
    CLUSTER_HANDLER_ON_OFF,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.SWITCH)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, Platform.SWITCH)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.SWITCH
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation switch from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.SWITCH]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_ON_OFF)
class Switch(ZhaEntity, SwitchEntity):
    """ZHA switch."""

    _attr_name: str = "Switch"

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Initialize the ZHA switch."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._on_off_cluster_handler = self.cluster_handlers[CLUSTER_HANDLER_ON_OFF]

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._on_off_cluster_handler.on_off is None:
            return False
        return self._on_off_cluster_handler.on_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        result = await self._on_off_cluster_handler.turn_on()
        if not result:
            return
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        result = await self._on_off_cluster_handler.turn_off()
        if not result:
            return
        self.async_write_ha_state()

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any):
        """Handle state update from cluster handler."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._on_off_cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the switch."""
        await super().async_update()
        if self._on_off_cluster_handler:
            await self._on_off_cluster_handler.get_attribute_value(
                "on_off", from_cache=False
            )


@GROUP_MATCH()
class SwitchGroup(ZhaGroupEntity, SwitchEntity):
    """Representation of a switch group."""

    def __init__(
        self,
        entity_ids: list[str],
        unique_id: str,
        group_id: int,
        zha_device: ZHADevice,
        **kwargs: Any,
    ) -> None:
        """Initialize a switch group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool
        self._state: bool
        group = self.zha_device.gateway.get_group(self._group_id)
        self._on_off_cluster_handler = group.endpoint[OnOff.cluster_id]

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        return bool(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        result = await self._on_off_cluster_handler.on()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        result = await self._on_off_cluster_handler.off()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._state = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Query all members and determine the switch group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._state = len(on_states) > 0
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)


class ZHASwitchConfigurationEntity(ZhaEntity, SwitchEntity):
    """Representation of a ZHA switch configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _zcl_attribute: str
    _zcl_inverter_attribute: str | None = None
    _force_inverted: bool = False

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        cluster_handler = cluster_handlers[0]
        if (
            cls._zcl_attribute in cluster_handler.cluster.unsupported_attributes
            or cls._zcl_attribute not in cluster_handler.cluster.attributes_by_name
            or cluster_handler.cluster.get(cls._zcl_attribute) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._zcl_attribute,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this number configuration entity."""
        self._cluster_handler: ClusterHandler = cluster_handlers[0]
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any):
        """Handle state update from cluster handler."""
        self.async_write_ha_state()

    @property
    def inverted(self) -> bool:
        """Return True if the switch is inverted."""
        if self._zcl_inverter_attribute:
            return bool(self._cluster_handler.cluster.get(self._zcl_inverter_attribute))
        return self._force_inverted

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        val = bool(self._cluster_handler.cluster.get(self._zcl_attribute))
        return (not val) if self.inverted else val

    async def async_turn_on_off(self, state: bool) -> None:
        """Turn the entity on or off."""
        try:
            result = await self._cluster_handler.cluster.write_attributes(
                {self._zcl_attribute: not state if self.inverted else state}
            )
        except zigpy.exceptions.ZigbeeException as ex:
            self.error("Could not set value: %s", ex)
            return
        if not isinstance(result, Exception) and all(
            record.status == Status.SUCCESS for record in result[0]
        ):
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_turn_on_off(False)

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        await super().async_update()
        self.error("Polling current state")
        if self._cluster_handler:
            value = await self._cluster_handler.get_attribute_value(
                self._zcl_attribute, from_cache=False
            )
            await self._cluster_handler.get_attribute_value(
                self._zcl_inverter_attribute, from_cache=False
            )
            self.debug("read value=%s, inverted=%s", value, self.inverted)


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_b6wax7g0",
    },
)
class OnOffWindowDetectionFunctionConfigurationEntity(
    ZHASwitchConfigurationEntity, id_suffix="on_off_window_opened_detection"
):
    """Representation of a ZHA window detection configuration entity."""

    _zcl_attribute: str = "window_detection_function"
    _zcl_inverter_attribute: str = "window_detection_function_inverter"
    _attr_name: str = "Invert window detection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.motion.ac02"}
)
class P1MotionTriggerIndicatorSwitch(
    ZHASwitchConfigurationEntity, id_suffix="trigger_indicator"
):
    """Representation of a ZHA motion triggering configuration entity."""

    _zcl_attribute: str = "trigger_indicator"
    _attr_name = "LED trigger indicator"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster",
    models={"lumi.plug.mmeu01", "lumi.plug.maeu01"},
)
class XiaomiPlugPowerOutageMemorySwitch(
    ZHASwitchConfigurationEntity, id_suffix="power_outage_memory"
):
    """Representation of a ZHA power outage memory configuration entity."""

    _zcl_attribute: str = "power_outage_memory"
    _attr_name = "Power outage memory"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_BASIC,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML001", "SML002", "SML003", "SML004"},
)
class HueMotionTriggerIndicatorSwitch(
    ZHASwitchConfigurationEntity, id_suffix="trigger_indicator"
):
    """Representation of a ZHA motion triggering configuration entity."""

    _zcl_attribute: str = "trigger_indicator"
    _attr_name = "LED trigger indicator"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class ChildLock(ZHASwitchConfigurationEntity, id_suffix="child_lock"):
    """ZHA BinarySensor."""

    _zcl_attribute: str = "child_lock"
    _attr_name = "Child lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class DisableLed(ZHASwitchConfigurationEntity, id_suffix="disable_led"):
    """ZHA BinarySensor."""

    _zcl_attribute: str = "disable_led"
    _attr_name = "Disable LED"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliInvertSwitch(ZHASwitchConfigurationEntity, id_suffix="invert_switch"):
    """Inovelli invert switch control."""

    _zcl_attribute: str = "invert_switch"
    _attr_name: str = "Invert switch"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliSmartBulbMode(ZHASwitchConfigurationEntity, id_suffix="smart_bulb_mode"):
    """Inovelli smart bulb mode control."""

    _zcl_attribute: str = "smart_bulb_mode"
    _attr_name: str = "Smart bulb mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDoubleTapUpEnabled(
    ZHASwitchConfigurationEntity, id_suffix="double_tap_up_enabled"
):
    """Inovelli double tap up enabled."""

    _zcl_attribute: str = "double_tap_up_enabled"
    _attr_name: str = "Double tap up enabled"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDoubleTapDownEnabled(
    ZHASwitchConfigurationEntity, id_suffix="double_tap_down_enabled"
):
    """Inovelli double tap down enabled."""

    _zcl_attribute: str = "double_tap_down_enabled"
    _attr_name: str = "Double tap down enabled"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliAuxSwitchScenes(
    ZHASwitchConfigurationEntity, id_suffix="aux_switch_scenes"
):
    """Inovelli unique aux switch scenes."""

    _zcl_attribute: str = "aux_switch_scenes"
    _attr_name: str = "Aux switch scenes"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliBindingOffToOnSyncLevel(
    ZHASwitchConfigurationEntity, id_suffix="binding_off_to_on_sync_level"
):
    """Inovelli send move to level with on/off to bound devices."""

    _zcl_attribute: str = "binding_off_to_on_sync_level"
    _attr_name: str = "Binding off to on sync level"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliLocalProtection(
    ZHASwitchConfigurationEntity, id_suffix="local_protection"
):
    """Inovelli local protection control."""

    _zcl_attribute: str = "local_protection"
    _attr_name: str = "Local protection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliOnOffLEDMode(ZHASwitchConfigurationEntity, id_suffix="on_off_led_mode"):
    """Inovelli only 1 LED mode control."""

    _zcl_attribute: str = "on_off_led_mode"
    _attr_name: str = "Only 1 LED mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliFirmwareProgressLED(
    ZHASwitchConfigurationEntity, id_suffix="firmware_progress_led"
):
    """Inovelli firmware progress LED control."""

    _zcl_attribute: str = "firmware_progress_led"
    _attr_name: str = "Firmware progress LED"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliRelayClickInOnOffMode(
    ZHASwitchConfigurationEntity, id_suffix="relay_click_in_on_off_mode"
):
    """Inovelli relay click in on off mode control."""

    _zcl_attribute: str = "relay_click_in_on_off_mode"
    _attr_name: str = "Disable relay click in on off mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDisableDoubleTapClearNotificationsMode(
    ZHASwitchConfigurationEntity, id_suffix="disable_clear_notifications_double_tap"
):
    """Inovelli disable clear notifications double tap control."""

    _zcl_attribute: str = "disable_clear_notifications_double_tap"
    _attr_name: str = "Disable config 2x tap to clear notifications"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
class AqaraPetFeederLEDIndicator(
    ZHASwitchConfigurationEntity, id_suffix="disable_led_indicator"
):
    """Representation of a LED indicator configuration entity."""

    _zcl_attribute: str = "disable_led_indicator"
    _attr_name = "LED indicator"
    _force_inverted = True
    _attr_icon: str = "mdi:led-on"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
class AqaraPetFeederChildLock(ZHASwitchConfigurationEntity, id_suffix="child_lock"):
    """Representation of a child lock configuration entity."""

    _zcl_attribute: str = "child_lock"
    _attr_name = "Child lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF,
    models={"TS011F"},
)
class TuyaChildLockSwitch(ZHASwitchConfigurationEntity, id_suffix="child_lock"):
    """Representation of a child lock configuration entity."""

    _zcl_attribute: str = "child_lock"
    _attr_name = "Child lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatWindowDetection(
    ZHASwitchConfigurationEntity, id_suffix="window_detection"
):
    """Representation of an Aqara thermostat window detection configuration entity."""

    _zcl_attribute: str = "window_detection"
    _attr_name = "Window detection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatValveDetection(
    ZHASwitchConfigurationEntity, id_suffix="valve_detection"
):
    """Representation of an Aqara thermostat valve detection configuration entity."""

    _zcl_attribute: str = "valve_detection"
    _attr_name = "Valve detection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatChildLock(ZHASwitchConfigurationEntity, id_suffix="child_lock"):
    """Representation of an Aqara thermostat child lock configuration entity."""

    _zcl_attribute: str = "child_lock"
    _attr_name = "Child lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraHeartbeatIndicator(
    ZHASwitchConfigurationEntity, id_suffix="heartbeat_indicator"
):
    """Representation of a heartbeat indicator configuration entity for Aqara smoke sensors."""

    _zcl_attribute: str = "heartbeat_indicator"
    _attr_name = "Heartbeat indicator"
    _attr_icon: str = "mdi:heart-flash"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraLinkageAlarm(ZHASwitchConfigurationEntity, id_suffix="linkage_alarm"):
    """Representation of a linkage alarm configuration entity for Aqara smoke sensors."""

    _zcl_attribute: str = "linkage_alarm"
    _attr_name = "Linkage alarm"
    _attr_icon: str = "mdi:shield-link-variant"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraBuzzerManualMute(
    ZHASwitchConfigurationEntity, id_suffix="buzzer_manual_mute"
):
    """Representation of a buzzer manual mute configuration entity for Aqara smoke sensors."""

    _zcl_attribute: str = "buzzer_manual_mute"
    _attr_name = "Buzzer manual mute"
    _attr_icon: str = "mdi:volume-off"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraBuzzerManualAlarm(
    ZHASwitchConfigurationEntity, id_suffix="buzzer_manual_alarm"
):
    """Representation of a buzzer manual mute configuration entity for Aqara smoke sensors."""

    _zcl_attribute: str = "buzzer_manual_alarm"
    _attr_name = "Buzzer manual alarm"
    _attr_icon: str = "mdi:bullhorn"
