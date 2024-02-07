"""Switches on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any, Self

from zhaquirks.quirk_ids import TUYA_PLUG_ONOFF
from zigpy.zcl.clusters.closures import ConfigStatus, WindowCovering, WindowCoveringMode
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
    CLUSTER_HANDLER_COVER,
    CLUSTER_HANDLER_INOVELLI,
    CLUSTER_HANDLER_ON_OFF,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.helpers import get_zha_data
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
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SWITCH]

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

    _attr_translation_key = "switch"

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
        await self._on_off_cluster_handler.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._on_off_cluster_handler.turn_off()
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
        self.debug("Polling current state")
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
        if result[1] is not Status.SUCCESS:
            return
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        result = await self._on_off_cluster_handler.off()
        if result[1] is not Status.SUCCESS:
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
    _attribute_name: str
    _inverter_attribute_name: str | None = None
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
            cls._attribute_name in cluster_handler.cluster.unsupported_attributes
            or cls._attribute_name not in cluster_handler.cluster.attributes_by_name
            or cluster_handler.cluster.get(cls._attribute_name) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._attribute_name,
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
        if self._inverter_attribute_name:
            return bool(
                self._cluster_handler.cluster.get(self._inverter_attribute_name)
            )
        return self._force_inverted

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        val = bool(self._cluster_handler.cluster.get(self._attribute_name))
        return (not val) if self.inverted else val

    async def async_turn_on_off(self, state: bool) -> None:
        """Turn the entity on or off."""
        await self._cluster_handler.write_attributes_safe(
            {self._attribute_name: not state if self.inverted else state}
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_turn_on_off(False)

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        self.debug("Polling current state")
        value = await self._cluster_handler.get_attribute_value(
            self._attribute_name, from_cache=False
        )
        await self._cluster_handler.get_attribute_value(
            self._inverter_attribute_name, from_cache=False
        )
        self.debug("read value=%s, inverted=%s", value, self.inverted)


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_b6wax7g0",
    },
)
class OnOffWindowDetectionFunctionConfigurationEntity(ZHASwitchConfigurationEntity):
    """Representation of a ZHA window detection configuration entity."""

    _unique_id_suffix = "on_off_window_opened_detection"
    _attribute_name = "window_detection_function"
    _inverter_attribute_name = "window_detection_function_inverter"
    _attr_translation_key = "window_detection_function"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.motion.ac02"}
)
class P1MotionTriggerIndicatorSwitch(ZHASwitchConfigurationEntity):
    """Representation of a ZHA motion triggering configuration entity."""

    _unique_id_suffix = "trigger_indicator"
    _attribute_name = "trigger_indicator"
    _attr_translation_key = "trigger_indicator"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster",
    models={"lumi.plug.mmeu01", "lumi.plug.maeu01"},
)
class XiaomiPlugPowerOutageMemorySwitch(ZHASwitchConfigurationEntity):
    """Representation of a ZHA power outage memory configuration entity."""

    _unique_id_suffix = "power_outage_memory"
    _attribute_name = "power_outage_memory"
    _attr_translation_key = "power_outage_memory"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_BASIC,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML001", "SML002", "SML003", "SML004"},
)
class HueMotionTriggerIndicatorSwitch(ZHASwitchConfigurationEntity):
    """Representation of a ZHA motion triggering configuration entity."""

    _unique_id_suffix = "trigger_indicator"
    _attribute_name = "trigger_indicator"
    _attr_translation_key = "trigger_indicator"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class ChildLock(ZHASwitchConfigurationEntity):
    """ZHA BinarySensor."""

    _unique_id_suffix = "child_lock"
    _attribute_name = "child_lock"
    _attr_translation_key = "child_lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class DisableLed(ZHASwitchConfigurationEntity):
    """ZHA BinarySensor."""

    _unique_id_suffix = "disable_led"
    _attribute_name = "disable_led"
    _attr_translation_key = "disable_led"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliInvertSwitch(ZHASwitchConfigurationEntity):
    """Inovelli invert switch control."""

    _unique_id_suffix = "invert_switch"
    _attribute_name = "invert_switch"
    _attr_translation_key = "invert_switch"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliSmartBulbMode(ZHASwitchConfigurationEntity):
    """Inovelli smart bulb mode control."""

    _unique_id_suffix = "smart_bulb_mode"
    _attribute_name = "smart_bulb_mode"
    _attr_translation_key = "smart_bulb_mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI, models={"VZM35-SN"}
)
class InovelliSmartFanMode(ZHASwitchConfigurationEntity):
    """Inovelli smart fan mode control."""

    _unique_id_suffix = "smart_fan_mode"
    _attribute_name = "smart_fan_mode"
    _attr_translation_key = "smart_fan_mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDoubleTapUpEnabled(ZHASwitchConfigurationEntity):
    """Inovelli double tap up enabled."""

    _unique_id_suffix = "double_tap_up_enabled"
    _attribute_name = "double_tap_up_enabled"
    _attr_translation_key = "double_tap_up_enabled"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDoubleTapDownEnabled(ZHASwitchConfigurationEntity):
    """Inovelli double tap down enabled."""

    _unique_id_suffix = "double_tap_down_enabled"
    _attribute_name = "double_tap_down_enabled"
    _attr_translation_key = "double_tap_down_enabled"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliAuxSwitchScenes(ZHASwitchConfigurationEntity):
    """Inovelli unique aux switch scenes."""

    _unique_id_suffix = "aux_switch_scenes"
    _attribute_name = "aux_switch_scenes"
    _attr_translation_key = "aux_switch_scenes"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliBindingOffToOnSyncLevel(ZHASwitchConfigurationEntity):
    """Inovelli send move to level with on/off to bound devices."""

    _unique_id_suffix = "binding_off_to_on_sync_level"
    _attribute_name = "binding_off_to_on_sync_level"
    _attr_translation_key = "binding_off_to_on_sync_level"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliLocalProtection(ZHASwitchConfigurationEntity):
    """Inovelli local protection control."""

    _unique_id_suffix = "local_protection"
    _attribute_name = "local_protection"
    _attr_translation_key = "local_protection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliOnOffLEDMode(ZHASwitchConfigurationEntity):
    """Inovelli only 1 LED mode control."""

    _unique_id_suffix = "on_off_led_mode"
    _attribute_name = "on_off_led_mode"
    _attr_translation_key = "one_led_mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliFirmwareProgressLED(ZHASwitchConfigurationEntity):
    """Inovelli firmware progress LED control."""

    _unique_id_suffix = "firmware_progress_led"
    _attribute_name = "firmware_progress_led"
    _attr_translation_key = "firmware_progress_led"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliRelayClickInOnOffMode(ZHASwitchConfigurationEntity):
    """Inovelli relay click in on off mode control."""

    _unique_id_suffix = "relay_click_in_on_off_mode"
    _attribute_name = "relay_click_in_on_off_mode"
    _attr_translation_key = "relay_click_in_on_off_mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliDisableDoubleTapClearNotificationsMode(ZHASwitchConfigurationEntity):
    """Inovelli disable clear notifications double tap control."""

    _unique_id_suffix = "disable_clear_notifications_double_tap"
    _attribute_name = "disable_clear_notifications_double_tap"
    _attr_translation_key = "disable_clear_notifications_double_tap"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
class AqaraPetFeederLEDIndicator(ZHASwitchConfigurationEntity):
    """Representation of a LED indicator configuration entity."""

    _unique_id_suffix = "disable_led_indicator"
    _attribute_name = "disable_led_indicator"
    _attr_translation_key = "led_indicator"
    _force_inverted = True
    _attr_icon: str = "mdi:led-on"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
class AqaraPetFeederChildLock(ZHASwitchConfigurationEntity):
    """Representation of a child lock configuration entity."""

    _unique_id_suffix = "child_lock"
    _attribute_name = "child_lock"
    _attr_translation_key = "child_lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF, quirk_ids=TUYA_PLUG_ONOFF
)
class TuyaChildLockSwitch(ZHASwitchConfigurationEntity):
    """Representation of a child lock configuration entity."""

    _unique_id_suffix = "child_lock"
    _attribute_name = "child_lock"
    _attr_translation_key = "child_lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatWindowDetection(ZHASwitchConfigurationEntity):
    """Representation of an Aqara thermostat window detection configuration entity."""

    _unique_id_suffix = "window_detection"
    _attribute_name = "window_detection"
    _attr_translation_key = "window_detection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatValveDetection(ZHASwitchConfigurationEntity):
    """Representation of an Aqara thermostat valve detection configuration entity."""

    _unique_id_suffix = "valve_detection"
    _attribute_name = "valve_detection"
    _attr_translation_key = "valve_detection"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatChildLock(ZHASwitchConfigurationEntity):
    """Representation of an Aqara thermostat child lock configuration entity."""

    _unique_id_suffix = "child_lock"
    _attribute_name = "child_lock"
    _attr_translation_key = "child_lock"
    _attr_icon: str = "mdi:account-lock"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraHeartbeatIndicator(ZHASwitchConfigurationEntity):
    """Representation of a heartbeat indicator configuration entity for Aqara smoke sensors."""

    _unique_id_suffix = "heartbeat_indicator"
    _attribute_name = "heartbeat_indicator"
    _attr_translation_key = "heartbeat_indicator"
    _attr_icon: str = "mdi:heart-flash"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraLinkageAlarm(ZHASwitchConfigurationEntity):
    """Representation of a linkage alarm configuration entity for Aqara smoke sensors."""

    _unique_id_suffix = "linkage_alarm"
    _attribute_name = "linkage_alarm"
    _attr_translation_key = "linkage_alarm"
    _attr_icon: str = "mdi:shield-link-variant"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraBuzzerManualMute(ZHASwitchConfigurationEntity):
    """Representation of a buzzer manual mute configuration entity for Aqara smoke sensors."""

    _unique_id_suffix = "buzzer_manual_mute"
    _attribute_name = "buzzer_manual_mute"
    _attr_translation_key = "buzzer_manual_mute"
    _attr_icon: str = "mdi:volume-off"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraBuzzerManualAlarm(ZHASwitchConfigurationEntity):
    """Representation of a buzzer manual mute configuration entity for Aqara smoke sensors."""

    _unique_id_suffix = "buzzer_manual_alarm"
    _attribute_name = "buzzer_manual_alarm"
    _attr_translation_key = "buzzer_manual_alarm"
    _attr_icon: str = "mdi:bullhorn"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_COVER)
class WindowCoveringInversionSwitch(ZHASwitchConfigurationEntity):
    """Representation of a switch that controls inversion for window covering devices.

    This is necessary because this cluster uses 2 attributes to control inversion.
    """

    _unique_id_suffix = "inverted"
    _attribute_name = WindowCovering.AttributeDefs.config_status.name
    _attr_translation_key = "inverted"
    _attr_icon: str = "mdi:arrow-up-down"

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
        window_covering_mode_attr = (
            WindowCovering.AttributeDefs.window_covering_mode.name
        )
        # this entity needs 2 attributes to function
        if (
            cls._attribute_name in cluster_handler.cluster.unsupported_attributes
            or cls._attribute_name not in cluster_handler.cluster.attributes_by_name
            or cluster_handler.cluster.get(cls._attribute_name) is None
            or window_covering_mode_attr
            in cluster_handler.cluster.unsupported_attributes
            or window_covering_mode_attr
            not in cluster_handler.cluster.attributes_by_name
            or cluster_handler.cluster.get(window_covering_mode_attr) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._attribute_name,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        config_status = ConfigStatus(
            self._cluster_handler.cluster.get(self._attribute_name)
        )
        return ConfigStatus.Open_up_commands_reversed in config_status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_on_off(False)

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        self.debug("Polling current state")
        await self._cluster_handler.get_attributes(
            [
                self._attribute_name,
                WindowCovering.AttributeDefs.window_covering_mode.name,
            ],
            from_cache=False,
            only_cache=False,
        )
        self.async_write_ha_state()

    async def _async_on_off(self, invert: bool) -> None:
        """Turn the entity on or off."""
        name: str = WindowCovering.AttributeDefs.window_covering_mode.name
        current_mode: WindowCoveringMode = WindowCoveringMode(
            self._cluster_handler.cluster.get(name)
        )
        send_command: bool = False
        if invert and WindowCoveringMode.Motor_direction_reversed not in current_mode:
            current_mode |= WindowCoveringMode.Motor_direction_reversed
            send_command = True
        elif not invert and WindowCoveringMode.Motor_direction_reversed in current_mode:
            current_mode &= ~WindowCoveringMode.Motor_direction_reversed
            send_command = True
        if send_command:
            await self._cluster_handler.write_attributes_safe({name: current_mode})
            await self.async_update()


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.curtain.agl001"}
)
class AqaraE1CurtainMotorHooksLockedSwitch(ZHASwitchConfigurationEntity):
    """Representation of a switch that controls whether the curtain motor hooks are locked."""

    _unique_id_suffix = "hooks_lock"
    _attribute_name = "hooks_lock"
    _attr_translation_key = "hooks_locked"
    _attr_icon: str = "mdi:lock"
