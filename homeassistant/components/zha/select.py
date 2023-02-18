"""Support for ZHA controls using the select platform."""
from __future__ import annotations

from enum import Enum
import functools
import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import Self
from zigpy import types
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
    CHANNEL_IAS_WD,
    CHANNEL_INOVELLI,
    CHANNEL_OCCUPANCY,
    CHANNEL_ON_OFF,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    Strobe,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.channels.base import ZigbeeChannel
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
    entities_to_create = hass.data[DATA_ZHA][Platform.SELECT]

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
    _attribute: str
    _enum: type[Enum]

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Init this select entity."""
        self._attribute = self._enum.__name__
        self._attr_options = [entry.name.replace("_", " ") for entry in self._enum]
        self._channel: ZigbeeChannel = channels[0]
        super().__init__(unique_id, zha_device, channels, **kwargs)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self._channel.data_cache.get(self._attribute)
        if option is None:
            return None
        return option.name.replace("_", " ")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._channel.data_cache[self._attribute] = self._enum[option.replace(" ", "_")]
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, last_state) -> None:
        """Restore previous state."""
        if last_state.state and last_state.state != STATE_UNKNOWN:
            self._channel.data_cache[self._attribute] = self._enum[
                last_state.state.replace(" ", "_")
            ]


class ZHANonZCLSelectEntity(ZHAEnumSelectEntity):
    """Representation of a ZHA select entity with no ZCL interaction."""

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True


@CONFIG_DIAGNOSTIC_MATCH(channel_names=CHANNEL_IAS_WD)
class ZHADefaultToneSelectEntity(
    ZHANonZCLSelectEntity, id_suffix=IasWd.Warning.WarningMode.__name__
):
    """Representation of a ZHA default siren tone select entity."""

    _enum = IasWd.Warning.WarningMode
    _attr_name = "Default siren tone"


@CONFIG_DIAGNOSTIC_MATCH(channel_names=CHANNEL_IAS_WD)
class ZHADefaultSirenLevelSelectEntity(
    ZHANonZCLSelectEntity, id_suffix=IasWd.Warning.SirenLevel.__name__
):
    """Representation of a ZHA default siren level select entity."""

    _enum = IasWd.Warning.SirenLevel
    _attr_name = "Default siren level"


@CONFIG_DIAGNOSTIC_MATCH(channel_names=CHANNEL_IAS_WD)
class ZHADefaultStrobeLevelSelectEntity(
    ZHANonZCLSelectEntity, id_suffix=IasWd.StrobeLevel.__name__
):
    """Representation of a ZHA default siren strobe level select entity."""

    _enum = IasWd.StrobeLevel
    _attr_name = "Default strobe level"


@CONFIG_DIAGNOSTIC_MATCH(channel_names=CHANNEL_IAS_WD)
class ZHADefaultStrobeSelectEntity(ZHANonZCLSelectEntity, id_suffix=Strobe.__name__):
    """Representation of a ZHA default siren strobe select entity."""

    _enum = Strobe
    _attr_name = "Default strobe"


class ZCLEnumSelectEntity(ZhaEntity, SelectEntity):
    """Representation of a ZHA ZCL enum select entity."""

    _select_attr: str
    _attr_entity_category = EntityCategory.CONFIG
    _enum: type[Enum]

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        channel = channels[0]
        if (
            cls._select_attr in channel.cluster.unsupported_attributes
            or channel.cluster.get(cls._select_attr) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._select_attr,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, channels, **kwargs)

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Init this select entity."""
        self._attr_options = [entry.name.replace("_", " ") for entry in self._enum]
        self._channel: ZigbeeChannel = channels[0]
        super().__init__(unique_id, zha_device, channels, **kwargs)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self._channel.cluster.get(self._select_attr)
        if option is None:
            return None
        option = self._enum(option)
        return option.name.replace("_", " ")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._channel.cluster.write_attributes(
            {self._select_attr: self._enum[option.replace(" ", "_")]}
        )
        self.async_write_ha_state()


@CONFIG_DIAGNOSTIC_MATCH(channel_names=CHANNEL_ON_OFF)
class ZHAStartupOnOffSelectEntity(
    ZCLEnumSelectEntity, id_suffix=OnOff.StartUpOnOff.__name__
):
    """Representation of a ZHA startup onoff select entity."""

    _select_attr = "start_up_on_off"
    _enum = OnOff.StartUpOnOff
    _attr_name = "Start-up behavior"


class TuyaPowerOnState(types.enum8):
    """Tuya power on state enum."""

    Off = 0x00
    On = 0x01
    LastState = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_ON_OFF,
    models={"TS011F", "TS0121", "TS0001", "TS0002", "TS0003", "TS0004"},
)
@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_7tdtqgwv",
        "_TZE200_amp6tsvy",
        "_TZE200_oisqyl4o",
        "_TZE200_vhy3iakz",
        "_TZ3000_uim07oem",
        "_TZE200_wfxuhoea",
        "_TZE200_tviaymwx",
        "_TZE200_g1ib5ldv",
        "_TZE200_wunufsil",
        "_TZE200_7deq70b8",
        "_TZE200_tz32mtza",
        "_TZE200_2hf7x9n3",
        "_TZE200_aqnazj70",
        "_TZE200_1ozguk6x",
        "_TZE200_k6jhsr0q",
        "_TZE200_9mahtqtg",
    },
)
class TuyaPowerOnStateSelectEntity(ZCLEnumSelectEntity, id_suffix="power_on_state"):
    """Representation of a ZHA power on state select entity."""

    _select_attr = "power_on_state"
    _enum = TuyaPowerOnState
    _attr_name = "Power on state"


class TuyaBacklightMode(types.enum8):
    """Tuya switch backlight mode enum."""

    Off = 0x00
    LightWhenOn = 0x01
    LightWhenOff = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_ON_OFF,
    models={"TS011F", "TS0121", "TS0001", "TS0002", "TS0003", "TS0004"},
)
class TuyaBacklightModeSelectEntity(ZCLEnumSelectEntity, id_suffix="backlight_mode"):
    """Representation of a ZHA backlight mode select entity."""

    _select_attr = "backlight_mode"
    _enum = TuyaBacklightMode
    _attr_name = "Backlight mode"


class MoesBacklightMode(types.enum8):
    """MOES switch backlight mode enum."""

    Off = 0x00
    LightWhenOn = 0x01
    LightWhenOff = 0x02
    Freeze = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_7tdtqgwv",
        "_TZE200_amp6tsvy",
        "_TZE200_oisqyl4o",
        "_TZE200_vhy3iakz",
        "_TZ3000_uim07oem",
        "_TZE200_wfxuhoea",
        "_TZE200_tviaymwx",
        "_TZE200_g1ib5ldv",
        "_TZE200_wunufsil",
        "_TZE200_7deq70b8",
        "_TZE200_tz32mtza",
        "_TZE200_2hf7x9n3",
        "_TZE200_aqnazj70",
        "_TZE200_1ozguk6x",
        "_TZE200_k6jhsr0q",
        "_TZE200_9mahtqtg",
    },
)
class MoesBacklightModeSelectEntity(ZCLEnumSelectEntity, id_suffix="backlight_mode"):
    """Moes devices have a different backlight mode select options."""

    _select_attr = "backlight_mode"
    _enum = MoesBacklightMode
    _attr_name = "Backlight mode"


class AqaraMotionSensitivities(types.enum8):
    """Aqara motion sensitivities."""

    Low = 0x01
    Medium = 0x02
    High = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="opple_cluster",
    models={"lumi.motion.ac01", "lumi.motion.ac02", "lumi.motion.agl04"},
)
class AqaraMotionSensitivity(ZCLEnumSelectEntity, id_suffix="motion_sensitivity"):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _select_attr = "motion_sensitivity"
    _enum = AqaraMotionSensitivities
    _attr_name = "Motion sensitivity"


class HueV1MotionSensitivities(types.enum8):
    """Hue v1 motion sensitivities."""

    Low = 0x00
    Medium = 0x01
    High = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_OCCUPANCY,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML001"},
)
class HueV1MotionSensitivity(ZCLEnumSelectEntity, id_suffix="motion_sensitivity"):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _select_attr = "sensitivity"
    _attr_name = "Hue motion sensitivity"
    _enum = HueV1MotionSensitivities


class HueV2MotionSensitivities(types.enum8):
    """Hue v2 motion sensitivities."""

    Lowest = 0x00
    Low = 0x01
    Medium = 0x02
    High = 0x03
    Highest = 0x04


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_OCCUPANCY,
    manufacturers={"Philips", "Signify Netherlands B.V."},
    models={"SML002", "SML003", "SML004"},
)
class HueV2MotionSensitivity(ZCLEnumSelectEntity, id_suffix="motion_sensitivity"):
    """Representation of a ZHA motion sensitivity configuration entity."""

    _select_attr = "sensitivity"
    _attr_name = "Hue motion sensitivity"
    _enum = HueV2MotionSensitivities


class AqaraMonitoringModess(types.enum8):
    """Aqara monitoring modes."""

    Undirected = 0x00
    Left_Right = 0x01


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"lumi.motion.ac01"})
class AqaraMonitoringMode(ZCLEnumSelectEntity, id_suffix="monitoring_mode"):
    """Representation of a ZHA monitoring mode configuration entity."""

    _select_attr = "monitoring_mode"
    _enum = AqaraMonitoringModess
    _attr_name = "Monitoring mode"


class AqaraApproachDistances(types.enum8):
    """Aqara approach distances."""

    Far = 0x00
    Medium = 0x01
    Near = 0x02


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"lumi.motion.ac01"})
class AqaraApproachDistance(ZCLEnumSelectEntity, id_suffix="approach_distance"):
    """Representation of a ZHA approach distance configuration entity."""

    _select_attr = "approach_distance"
    _enum = AqaraApproachDistances
    _attr_name = "Approach distance"


class AqaraE1ReverseDirection(types.enum8):
    """Aqara curtain reversal."""

    Normal = 0x00
    Inverted = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="window_covering", models={"lumi.curtain.agl001"}
)
class AqaraCurtainMode(ZCLEnumSelectEntity, id_suffix="window_covering_mode"):
    """Representation of a ZHA curtain mode configuration entity."""

    _select_attr = "window_covering_mode"
    _enum = AqaraE1ReverseDirection
    _attr_name = "Curtain mode"


class InovelliOutputMode(types.enum1):
    """Inovelli output mode."""

    Dimmer = 0x00
    OnOff = 0x01


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_INOVELLI,
)
class InovelliOutputModeEntity(ZCLEnumSelectEntity, id_suffix="output_mode"):
    """Inovelli output mode control."""

    _select_attr = "output_mode"
    _enum = InovelliOutputMode
    _attr_name: str = "Output mode"


class InovelliSwitchType(types.enum8):
    """Inovelli output mode."""

    Load_Only = 0x00
    Three_Way_Dumb = 0x01
    Three_Way_AUX = 0x02


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names=CHANNEL_INOVELLI,
)
class InovelliSwitchTypeEntity(ZCLEnumSelectEntity, id_suffix="switch_type"):
    """Inovelli switch type control."""

    _select_attr = "switch_type"
    _enum = InovelliSwitchType
    _attr_name: str = "Switch type"


class AqaraFeedingMode(types.enum8):
    """Feeding mode."""

    Manual = 0x00
    Schedule = 0x01


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"aqara.feeder.acn001"})
class AqaraPetFeederMode(ZCLEnumSelectEntity, id_suffix="feeding_mode"):
    """Representation of an Aqara pet feeder mode configuration entity."""

    _select_attr = "feeding_mode"
    _enum = AqaraFeedingMode
    _attr_name = "Mode"
    _attr_icon: str = "mdi:wrench-clock"
