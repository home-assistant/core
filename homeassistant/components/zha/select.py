"""Support for ZHA controls using the select platform."""

from __future__ import annotations

from enum import Enum
import functools
import logging
from typing import TYPE_CHECKING, Any, Self

from zhaquirks.quirk_ids import TUYA_PLUG_MANUFACTURER, TUYA_PLUG_ONOFF
from zhaquirks.xiaomi.aqara.magnet_ac01 import OppleCluster as MagnetAC01OppleCluster
from zhaquirks.xiaomi.aqara.switch_acn047 import OppleCluster as T2RelayOppleCluster
from zigpy import types
from zigpy.quirks.v2 import ZCLEnumMetadata
from zigpy.zcl.clusters.general import OnOff
from zigpy.zcl.clusters.security import IasWd

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_HUE_OCCUPANCY,
    CLUSTER_HANDLER_IAS_WD,
    CLUSTER_HANDLER_INOVELLI,
    CLUSTER_HANDLER_OCCUPANCY,
    CLUSTER_HANDLER_ON_OFF,
    ENTITY_METADATA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    Strobe,
)
from .core.helpers import get_zha_data
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice


CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.SELECT
)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation siren from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SELECT]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAEnumSelectEntity(ZhaEntity, SelectEntity):
    """Representation of a ZHA select entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attribute_name: str
    _enum: type[Enum]

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this select entity."""
        self._cluster_handler: ClusterHandler = cluster_handlers[0]
        self._attribute_name = self._enum.__name__
        self._attr_options = [entry.name.replace("_", " ") for entry in self._enum]
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self._cluster_handler.data_cache.get(self._attribute_name)
        if option is None:
            return None
        return option.name.replace("_", " ")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._cluster_handler.data_cache[self._attribute_name] = self._enum[
            option.replace(" ", "_")
        ]
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, last_state) -> None:
        """Restore previous state."""
        if last_state.state and last_state.state != STATE_UNKNOWN:
            self._cluster_handler.data_cache[self._attribute_name] = self._enum[
                last_state.state.replace(" ", "_")
            ]


class ZHANonZCLSelectEntity(ZHAEnumSelectEntity):
    """Representation of a ZHA select entity with no ZCL interaction."""

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_IAS_WD)
class ZHADefaultToneSelectEntity(ZHANonZCLSelectEntity):
    """Representation of a ZHA default siren tone select entity."""

    _unique_id_suffix = IasWd.Warning.WarningMode.__name__
    _enum = IasWd.Warning.WarningMode
    _attr_translation_key: str = "default_siren_tone"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_IAS_WD)
class ZHADefaultSirenLevelSelectEntity(ZHANonZCLSelectEntity):
    """Representation of a ZHA default siren level select entity."""

    _unique_id_suffix = IasWd.Warning.SirenLevel.__name__
    _enum = IasWd.Warning.SirenLevel
    _attr_translation_key: str = "default_siren_level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_IAS_WD)
class ZHADefaultStrobeLevelSelectEntity(ZHANonZCLSelectEntity):
    """Representation of a ZHA default siren strobe level select entity."""

    _unique_id_suffix = IasWd.StrobeLevel.__name__
    _enum = IasWd.StrobeLevel
    _attr_translation_key: str = "default_strobe_level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_IAS_WD)
class ZHADefaultStrobeSelectEntity(ZHANonZCLSelectEntity):
    """Representation of a ZHA default siren strobe select entity."""

    _unique_id_suffix = Strobe.__name__
    _enum = Strobe
    _attr_translation_key: str = "default_strobe"


class ZCLEnumSelectEntity(ZhaEntity, SelectEntity):
    """Representation of a ZHA ZCL enum select entity."""

    _attribute_name: str
    _attr_entity_category = EntityCategory.CONFIG
    _enum: type[Enum]

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
        if ENTITY_METADATA not in kwargs and (
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
        """Init this select entity."""
        self._cluster_handler: ClusterHandler = cluster_handlers[0]
        if ENTITY_METADATA in kwargs:
            self._init_from_quirks_metadata(kwargs[ENTITY_METADATA])
        self._attr_options = [entry.name.replace("_", " ") for entry in self._enum]
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

    def _init_from_quirks_metadata(self, entity_metadata: ZCLEnumMetadata) -> None:
        """Init this entity from the quirks metadata."""
        super()._init_from_quirks_metadata(entity_metadata)
        self._attribute_name = entity_metadata.attribute_name
        self._enum = entity_metadata.enum

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self._cluster_handler.cluster.get(self._attribute_name)
        if option is None:
            return None
        option = self._enum(option)
        return option.name.replace("_", " ")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._cluster_handler.write_attributes_safe(
            {self._attribute_name: self._enum[option.replace(" ", "_")]}
        )
        self.async_write_ha_state()

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


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_ON_OFF)
class ZHAStartupOnOffSelectEntity(ZCLEnumSelectEntity):
    """Representation of a ZHA startup onoff select entity."""

    _unique_id_suffix = OnOff.StartUpOnOff.__name__
    _attribute_name = "start_up_on_off"
    _enum = OnOff.StartUpOnOff
    _attr_translation_key: str = "start_up_on_off"


class TuyaPowerOnState(types.enum8):
    """Tuya power on state enum."""

    Off = 0x00
    On = 0x01
    LastState = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF, quirk_ids=TUYA_PLUG_ONOFF
)
@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer", quirk_ids=TUYA_PLUG_MANUFACTURER
)
class TuyaPowerOnStateSelectEntity(ZCLEnumSelectEntity):
    """Representation of a ZHA power on state select entity."""

    _unique_id_suffix = "power_on_state"
    _attribute_name = "power_on_state"
    _enum = TuyaPowerOnState
    _attr_translation_key: str = "power_on_state"


class TuyaBacklightMode(types.enum8):
    """Tuya switch backlight mode enum."""

    Off = 0x00
    LightWhenOn = 0x01
    LightWhenOff = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF, quirk_ids=TUYA_PLUG_ONOFF
)
class TuyaBacklightModeSelectEntity(ZCLEnumSelectEntity):
    """Representation of a ZHA backlight mode select entity."""

    _unique_id_suffix = "backlight_mode"
    _attribute_name = "backlight_mode"
    _enum = TuyaBacklightMode
    _attr_translation_key: str = "backlight_mode"


class MoesBacklightMode(types.enum8):
    """MOES switch backlight mode enum."""

    Off = 0x00
    LightWhenOn = 0x01
    LightWhenOff = 0x02
    Freeze = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer", quirk_ids=TUYA_PLUG_MANUFACTURER
)
class MoesBacklightModeSelectEntity(ZCLEnumSelectEntity):
    """Moes devices have a different backlight mode select options."""

    _unique_id_suffix = "backlight_mode"
    _attribute_name = "backlight_mode"
    _enum = MoesBacklightMode
    _attr_translation_key: str = "backlight_mode"


class AqaraMotionSensitivities(types.enum8):
    """Aqara motion sensitivities."""

    Low = 0x01
    Medium = 0x02
    High = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster",
    models={"lumi.motion.ac01", "lumi.motion.ac02", "lumi.motion.agl04"},
)
class AqaraMotionSensitivity(ZCLEnumSelectEntity):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _unique_id_suffix = "motion_sensitivity"
    _attribute_name = "motion_sensitivity"
    _enum = AqaraMotionSensitivities
    _attr_translation_key: str = "motion_sensitivity"


class HueV1MotionSensitivities(types.enum8):
    """Hue v1 motion sensitivities."""

    Low = 0x00
    Medium = 0x01
    High = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_HUE_OCCUPANCY,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML001"},
)
class HueV1MotionSensitivity(ZCLEnumSelectEntity):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _unique_id_suffix = "motion_sensitivity"
    _attribute_name = "sensitivity"
    _enum = HueV1MotionSensitivities
    _attr_translation_key: str = "motion_sensitivity"


class HueV2MotionSensitivities(types.enum8):
    """Hue v2 motion sensitivities."""

    Lowest = 0x00
    Low = 0x01
    Medium = 0x02
    High = 0x03
    Highest = 0x04


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_HUE_OCCUPANCY,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML002", "SML003", "SML004"},
)
class HueV2MotionSensitivity(ZCLEnumSelectEntity):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _unique_id_suffix = "motion_sensitivity"
    _attribute_name = "sensitivity"
    _enum = HueV2MotionSensitivities
    _attr_translation_key: str = "motion_sensitivity"


class AqaraMonitoringModess(types.enum8):
    """Aqara monitoring modes."""

    Undirected = 0x00
    Left_Right = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.motion.ac01"}
)
class AqaraMonitoringMode(ZCLEnumSelectEntity):
    """Representation of a ZHA monitoring mode configuration entity."""

    _unique_id_suffix = "monitoring_mode"
    _attribute_name = "monitoring_mode"
    _enum = AqaraMonitoringModess
    _attr_translation_key: str = "monitoring_mode"


class AqaraApproachDistances(types.enum8):
    """Aqara approach distances."""

    Far = 0x00
    Medium = 0x01
    Near = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.motion.ac01"}
)
class AqaraApproachDistance(ZCLEnumSelectEntity):
    """Representation of a ZHA approach distance configuration entity."""

    _unique_id_suffix = "approach_distance"
    _attribute_name = "approach_distance"
    _enum = AqaraApproachDistances
    _attr_translation_key: str = "approach_distance"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.magnet.ac01"}
)
class AqaraMagnetAC01DetectionDistance(ZCLEnumSelectEntity):
    """Representation of a ZHA detection distance configuration entity."""

    _unique_id_suffix = "detection_distance"
    _attribute_name = "detection_distance"
    _enum = MagnetAC01OppleCluster.DetectionDistance
    _attr_translation_key: str = "detection_distance"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.switch.acn047"}
)
class AqaraT2RelaySwitchMode(ZCLEnumSelectEntity):
    """Representation of a ZHA switch mode configuration entity."""

    _unique_id_suffix = "switch_mode"
    _attribute_name = "switch_mode"
    _enum = T2RelayOppleCluster.SwitchMode
    _attr_translation_key: str = "switch_mode"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.switch.acn047"}
)
class AqaraT2RelaySwitchType(ZCLEnumSelectEntity):
    """Representation of a ZHA switch type configuration entity."""

    _unique_id_suffix = "switch_type"
    _attribute_name = "switch_type"
    _enum = T2RelayOppleCluster.SwitchType
    _attr_translation_key: str = "switch_type"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.switch.acn047"}
)
class AqaraT2RelayStartupOnOff(ZCLEnumSelectEntity):
    """Representation of a ZHA startup on off configuration entity."""

    _unique_id_suffix = "startup_on_off"
    _attribute_name = "startup_on_off"
    _enum = T2RelayOppleCluster.StartupOnOff
    _attr_translation_key: str = "start_up_on_off"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.switch.acn047"}
)
class AqaraT2RelayDecoupledMode(ZCLEnumSelectEntity):
    """Representation of a ZHA switch decoupled mode configuration entity."""

    _unique_id_suffix = "decoupled_mode"
    _attribute_name = "decoupled_mode"
    _enum = T2RelayOppleCluster.DecoupledMode
    _attr_translation_key: str = "decoupled_mode"


class InovelliOutputMode(types.enum1):
    """Inovelli output mode."""

    Dimmer = 0x00
    OnOff = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliOutputModeEntity(ZCLEnumSelectEntity):
    """Inovelli output mode control."""

    _unique_id_suffix = "output_mode"
    _attribute_name = "output_mode"
    _enum = InovelliOutputMode
    _attr_translation_key: str = "output_mode"


class InovelliSwitchType(types.enum8):
    """Inovelli switch mode."""

    Single_Pole = 0x00
    Three_Way_Dumb = 0x01
    Three_Way_AUX = 0x02
    Single_Pole_Full_Sine = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI, models={"VZM31-SN"}
)
class InovelliSwitchTypeEntity(ZCLEnumSelectEntity):
    """Inovelli switch type control."""

    _unique_id_suffix = "switch_type"
    _attribute_name = "switch_type"
    _enum = InovelliSwitchType
    _attr_translation_key: str = "switch_type"


class InovelliFanSwitchType(types.enum1):
    """Inovelli fan switch mode."""

    Load_Only = 0x00
    Three_Way_AUX = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI, models={"VZM35-SN"}
)
class InovelliFanSwitchTypeEntity(ZCLEnumSelectEntity):
    """Inovelli fan switch type control."""

    _unique_id_suffix = "switch_type"
    _attribute_name = "switch_type"
    _enum = InovelliFanSwitchType
    _attr_translation_key: str = "switch_type"


class InovelliLedScalingMode(types.enum1):
    """Inovelli led mode."""

    VZM31SN = 0x00
    LZW31SN = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliLedScalingModeEntity(ZCLEnumSelectEntity):
    """Inovelli led mode control."""

    _unique_id_suffix = "led_scaling_mode"
    _attribute_name = "led_scaling_mode"
    _enum = InovelliLedScalingMode
    _attr_translation_key: str = "led_scaling_mode"


class InovelliFanLedScalingMode(types.enum8):
    """Inovelli fan led mode."""

    VZM31SN = 0x00
    Grade_1 = 0x01
    Grade_2 = 0x02
    Grade_3 = 0x03
    Grade_4 = 0x04
    Grade_5 = 0x05
    Grade_6 = 0x06
    Grade_7 = 0x07
    Grade_8 = 0x08
    Grade_9 = 0x09
    Adaptive = 0x0A


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI, models={"VZM35-SN"}
)
class InovelliFanLedScalingModeEntity(ZCLEnumSelectEntity):
    """Inovelli fan switch led mode control."""

    _unique_id_suffix = "smart_fan_led_display_levels"
    _attribute_name = "smart_fan_led_display_levels"
    _enum = InovelliFanLedScalingMode
    _attr_translation_key: str = "smart_fan_led_display_levels"


class InovelliNonNeutralOutput(types.enum1):
    """Inovelli non neutral output selection."""

    Low = 0x00
    High = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_INOVELLI,
)
class InovelliNonNeutralOutputEntity(ZCLEnumSelectEntity):
    """Inovelli non neutral output control."""

    _unique_id_suffix = "increased_non_neutral_output"
    _attribute_name = "increased_non_neutral_output"
    _enum = InovelliNonNeutralOutput
    _attr_translation_key: str = "increased_non_neutral_output"


class AqaraFeedingMode(types.enum8):
    """Feeding mode."""

    Manual = 0x00
    Schedule = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
class AqaraPetFeederMode(ZCLEnumSelectEntity):
    """Representation of an Aqara pet feeder mode configuration entity."""

    _unique_id_suffix = "feeding_mode"
    _attribute_name = "feeding_mode"
    _enum = AqaraFeedingMode
    _attr_translation_key: str = "feeding_mode"


class AqaraThermostatPresetMode(types.enum8):
    """Thermostat preset mode."""

    Manual = 0x00
    Auto = 0x01
    Away = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatPreset(ZCLEnumSelectEntity):
    """Representation of an Aqara thermostat preset configuration entity."""

    _unique_id_suffix = "preset"
    _attribute_name = "preset"
    _enum = AqaraThermostatPresetMode
    _attr_translation_key: str = "preset"


class SonoffPresenceDetectionSensitivityEnum(types.enum8):
    """Enum for detection sensitivity select entity."""

    Low = 0x01
    Medium = 0x02
    High = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_OCCUPANCY, models={"SNZB-06P"}
)
class SonoffPresenceDetectionSensitivity(ZCLEnumSelectEntity):
    """Entity to set the detection sensitivity of the Sonoff SNZB-06P."""

    _unique_id_suffix = "detection_sensitivity"
    _attribute_name = "ultrasonic_u_to_o_threshold"
    _enum = SonoffPresenceDetectionSensitivityEnum
    _attr_translation_key: str = "detection_sensitivity"


class KeypadLockoutEnum(types.enum8):
    """Keypad lockout options."""

    Unlock = 0x00
    Lock1 = 0x01
    Lock2 = 0x02
    Lock3 = 0x03
    Lock4 = 0x04


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names="thermostat_ui")
class KeypadLockout(ZCLEnumSelectEntity):
    """Mandatory attribute for thermostat_ui cluster.

    Often only the first two are implemented, and Lock2 to Lock4 should map to Lock1 in the firmware.
    This however covers all bases.
    """

    _unique_id_suffix = "keypad_lockout"
    _attribute_name: str = "keypad_lockout"
    _enum = KeypadLockoutEnum
    _attr_translation_key: str = "keypad_lockout"
