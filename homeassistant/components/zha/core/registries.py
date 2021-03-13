"""Mapping registries for Zigbee Home Automation."""
from __future__ import annotations

import collections
from typing import Callable, Dict

import attr
import zigpy.profiles.zha
import zigpy.profiles.zll
import zigpy.zcl as zcl

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.number import DOMAIN as NUMBER
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

# importing channels updates registries
from . import channels as zha_channels  # noqa: F401 pylint: disable=unused-import
from .decorators import CALLABLE_T, DictRegistry, SetRegistry
from .typing import ChannelType

GROUP_ENTITY_DOMAINS = [LIGHT, SWITCH, FAN]

PHILLIPS_REMOTE_CLUSTER = 0xFC00
SMARTTHINGS_ACCELERATION_CLUSTER = 0xFC02
SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE = 0x8000
SMARTTHINGS_HUMIDITY_CLUSTER = 0xFC45

REMOTE_DEVICE_TYPES = {
    zigpy.profiles.zha.PROFILE_ID: [
        zigpy.profiles.zha.DeviceType.COLOR_CONTROLLER,
        zigpy.profiles.zha.DeviceType.COLOR_DIMMER_SWITCH,
        zigpy.profiles.zha.DeviceType.COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zha.DeviceType.DIMMER_SWITCH,
        zigpy.profiles.zha.DeviceType.LEVEL_CONTROL_SWITCH,
        zigpy.profiles.zha.DeviceType.NON_COLOR_CONTROLLER,
        zigpy.profiles.zha.DeviceType.NON_COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
        zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT_SWITCH,
        zigpy.profiles.zha.DeviceType.REMOTE_CONTROL,
        zigpy.profiles.zha.DeviceType.SCENE_SELECTOR,
    ],
    zigpy.profiles.zll.PROFILE_ID: [
        zigpy.profiles.zll.DeviceType.COLOR_CONTROLLER,
        zigpy.profiles.zll.DeviceType.COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zll.DeviceType.CONTROL_BRIDGE,
        zigpy.profiles.zll.DeviceType.CONTROLLER,
        zigpy.profiles.zll.DeviceType.SCENE_CONTROLLER,
    ],
}
REMOTE_DEVICE_TYPES = collections.defaultdict(list, REMOTE_DEVICE_TYPES)

SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {
    # this works for now but if we hit conflicts we can break it out to
    # a different dict that is keyed by manufacturer
    SMARTTHINGS_ACCELERATION_CLUSTER: BINARY_SENSOR,
    SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR,
    zcl.clusters.closures.DoorLock.cluster_id: LOCK,
    zcl.clusters.closures.WindowCovering.cluster_id: COVER,
    zcl.clusters.general.AnalogInput.cluster_id: SENSOR,
    zcl.clusters.general.AnalogOutput.cluster_id: NUMBER,
    zcl.clusters.general.MultistateInput.cluster_id: SENSOR,
    zcl.clusters.general.OnOff.cluster_id: SWITCH,
    zcl.clusters.general.PowerConfiguration.cluster_id: SENSOR,
    zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id: SENSOR,
    zcl.clusters.hvac.Fan.cluster_id: FAN,
    zcl.clusters.measurement.CarbonDioxideConcentration.cluster_id: SENSOR,
    zcl.clusters.measurement.CarbonMonoxideConcentration.cluster_id: SENSOR,
    zcl.clusters.measurement.IlluminanceMeasurement.cluster_id: SENSOR,
    zcl.clusters.measurement.OccupancySensing.cluster_id: BINARY_SENSOR,
    zcl.clusters.measurement.PressureMeasurement.cluster_id: SENSOR,
    zcl.clusters.measurement.RelativeHumidity.cluster_id: SENSOR,
    zcl.clusters.measurement.TemperatureMeasurement.cluster_id: SENSOR,
    zcl.clusters.security.IasZone.cluster_id: BINARY_SENSOR,
    zcl.clusters.smartenergy.Metering.cluster_id: SENSOR,
}

SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {
    zcl.clusters.general.OnOff.cluster_id: BINARY_SENSOR
}

BINDABLE_CLUSTERS = SetRegistry()
CHANNEL_ONLY_CLUSTERS = SetRegistry()

DEVICE_CLASS = {
    zigpy.profiles.zha.PROFILE_ID: {
        SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE: DEVICE_TRACKER,
        zigpy.profiles.zha.DeviceType.THERMOSTAT: CLIMATE,
        zigpy.profiles.zha.DeviceType.COLOR_DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_BALLAST: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_PLUG_IN_UNIT: LIGHT,
        zigpy.profiles.zha.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: COVER,
        zigpy.profiles.zha.DeviceType.ON_OFF_BALLAST: SWITCH,
        zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.ON_OFF_PLUG_IN_UNIT: SWITCH,
        zigpy.profiles.zha.DeviceType.SHADE: COVER,
        zigpy.profiles.zha.DeviceType.SMART_PLUG: SWITCH,
        zigpy.profiles.zha.DeviceType.IAS_ANCILLARY_CONTROL: ALARM,
    },
    zigpy.profiles.zll.PROFILE_ID: {
        zigpy.profiles.zll.DeviceType.COLOR_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_PLUGIN_UNIT: LIGHT,
        zigpy.profiles.zll.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_PLUGIN_UNIT: SWITCH,
    },
}
DEVICE_CLASS = collections.defaultdict(dict, DEVICE_CLASS)

CLIENT_CHANNELS_REGISTRY = DictRegistry()

ZIGBEE_CHANNEL_REGISTRY = DictRegistry()


def set_or_callable(value):
    """Convert single str or None to a set. Pass through callables and sets."""
    if value is None:
        return frozenset()
    if callable(value):
        return value
    if isinstance(value, (frozenset, set, list)):
        return frozenset(value)
    return frozenset([str(value)])


@attr.s(frozen=True)
class MatchRule:
    """Match a ZHA Entity to a channel name or generic id."""

    channel_names: Callable | set[str] | str = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    generic_ids: Callable | set[str] | str = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    manufacturers: Callable | set[str] | str = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    models: Callable | set[str] | str = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    aux_channels: Callable | set[str] | str = attr.ib(
        factory=frozenset, converter=set_or_callable
    )

    @property
    def weight(self) -> int:
        """Return the weight of the matching rule.

        Most specific matches should be preferred over less specific. Model matching
        rules have a priority over manufacturer matching rules and rules matching a
        single model/manufacturer get a better priority over rules matching multiple
        models/manufacturers. And any model or manufacturers matching rules get better
        priority over rules matching only channels.
        But in case of a channel name/channel id matching, we give rules matching
        multiple channels a better priority over rules matching a single channel.
        """
        weight = 0
        if self.models:
            weight += 401 - (1 if callable(self.models) else len(self.models))

        if self.manufacturers:
            weight += 301 - (
                1 if callable(self.manufacturers) else len(self.manufacturers)
            )

        weight += 10 * len(self.channel_names)
        weight += 5 * len(self.generic_ids)
        weight += 1 * len(self.aux_channels)
        return weight

    def claim_channels(self, channel_pool: list[ChannelType]) -> list[ChannelType]:
        """Return a list of channels this rule matches + aux channels."""
        claimed = []
        if isinstance(self.channel_names, frozenset):
            claimed.extend([ch for ch in channel_pool if ch.name in self.channel_names])
        if isinstance(self.generic_ids, frozenset):
            claimed.extend(
                [ch for ch in channel_pool if ch.generic_id in self.generic_ids]
            )
        if isinstance(self.aux_channels, frozenset):
            claimed.extend([ch for ch in channel_pool if ch.name in self.aux_channels])
        return claimed

    def strict_matched(self, manufacturer: str, model: str, channels: list) -> bool:
        """Return True if this device matches the criteria."""
        return all(self._matched(manufacturer, model, channels))

    def loose_matched(self, manufacturer: str, model: str, channels: list) -> bool:
        """Return True if this device matches the criteria."""
        return any(self._matched(manufacturer, model, channels))

    def _matched(self, manufacturer: str, model: str, channels: list) -> list:
        """Return a list of field matches."""
        if not any(attr.asdict(self).values()):
            return [False]

        matches = []
        if self.channel_names:
            channel_names = {ch.name for ch in channels}
            matches.append(self.channel_names.issubset(channel_names))

        if self.generic_ids:
            all_generic_ids = {ch.generic_id for ch in channels}
            matches.append(self.generic_ids.issubset(all_generic_ids))

        if self.manufacturers:
            if callable(self.manufacturers):
                matches.append(self.manufacturers(manufacturer))
            else:
                matches.append(manufacturer in self.manufacturers)

        if self.models:
            if callable(self.models):
                matches.append(self.models(model))
            else:
                matches.append(model in self.models)

        return matches


RegistryDictType = Dict[str, Dict[MatchRule, CALLABLE_T]]

GroupRegistryDictType = Dict[str, CALLABLE_T]


class ZHAEntityRegistry:
    """Channel to ZHA Entity mapping."""

    def __init__(self):
        """Initialize Registry instance."""
        self._strict_registry: RegistryDictType = collections.defaultdict(dict)
        self._loose_registry: RegistryDictType = collections.defaultdict(dict)
        self._group_registry: GroupRegistryDictType = {}

    def get_entity(
        self,
        component: str,
        manufacturer: str,
        model: str,
        channels: list[ChannelType],
        default: CALLABLE_T = None,
    ) -> tuple[CALLABLE_T, list[ChannelType]]:
        """Match a ZHA Channels to a ZHA Entity class."""
        matches = self._strict_registry[component]
        for match in sorted(matches, key=lambda x: x.weight, reverse=True):
            if match.strict_matched(manufacturer, model, channels):
                claimed = match.claim_channels(channels)
                return self._strict_registry[component][match], claimed

        return default, []

    def get_group_entity(self, component: str) -> CALLABLE_T:
        """Match a ZHA group to a ZHA Entity class."""
        return self._group_registry.get(component)

    def strict_match(
        self,
        component: str,
        channel_names: Callable | set[str] | str = None,
        generic_ids: Callable | set[str] | str = None,
        manufacturers: Callable | set[str] | str = None,
        models: Callable | set[str] | str = None,
        aux_channels: Callable | set[str] | str = None,
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a strict match rule."""

        rule = MatchRule(
            channel_names, generic_ids, manufacturers, models, aux_channels
        )

        def decorator(zha_ent: CALLABLE_T) -> CALLABLE_T:
            """Register a strict match rule.

            All non empty fields of a match rule must match.
            """
            self._strict_registry[component][rule] = zha_ent
            return zha_ent

        return decorator

    def loose_match(
        self,
        component: str,
        channel_names: Callable | set[str] | str = None,
        generic_ids: Callable | set[str] | str = None,
        manufacturers: Callable | set[str] | str = None,
        models: Callable | set[str] | str = None,
        aux_channels: Callable | set[str] | str = None,
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a loose match rule."""

        rule = MatchRule(
            channel_names, generic_ids, manufacturers, models, aux_channels
        )

        def decorator(zha_entity: CALLABLE_T) -> CALLABLE_T:
            """Register a loose match rule.

            All non empty fields of a match rule must match.
            """
            self._loose_registry[component][rule] = zha_entity
            return zha_entity

        return decorator

    def group_match(self, component: str) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a group match rule."""

        def decorator(zha_ent: CALLABLE_T) -> CALLABLE_T:
            """Register a group match rule."""
            self._group_registry[component] = zha_ent
            return zha_ent

        return decorator


ZHA_ENTITIES = ZHAEntityRegistry()
